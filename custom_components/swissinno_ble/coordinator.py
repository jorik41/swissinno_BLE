"""Data coordinator for the Swissinno BLE integration."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_last_service_info,
    async_process_advertisements,
    async_register_callback,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .const import (
    BATTERY_MAX_VOLTAGE,
    BATTERY_MAX_VOLTAGE_RECHARGEABLE,
    BATTERY_MIN_VOLTAGE,
    BATTERY_MIN_VOLTAGE_RECHARGEABLE,
    DOMAIN,
    MANUFACTURER_IDS,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class SwissinnoTrapData:
    """Represent data parsed from Swissinno Bluetooth advertisements."""

    triggered: bool | None = None
    voltage: float | None = None
    battery: int | None = None
    raw: str | None = None
    last_update: datetime | None = None


class SwissinnoBLECoordinator(DataUpdateCoordinator[SwissinnoTrapData]):
    """Coordinator to handle Swissinno BLE advertisements."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        rechargeable: bool,
        debug: bool,
        update_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}-{address}",
            update_interval=timedelta(seconds=update_interval),
        )
        self.address = address
        self._ble_address = address.upper()
        self.rechargeable = rechargeable
        self.debug = debug
        self.data = SwissinnoTrapData()
        self._missing_logged = False
        self._matcher = BluetoothCallbackMatcher(address=self._ble_address)
        self._unsub = async_register_callback(
            hass,
            self._async_handle_ble_event,
            self._matcher,
            BluetoothScanningMode.PASSIVE,
        )
        self._last_service_info_time: float | None = None

    def _async_handle_ble_event(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Handle incoming Bluetooth advertisement."""
        manufacturer_data = self._parse_manufacturer_data(service_info)
        if not manufacturer_data:
            if self.debug:
                _LOGGER.debug(
                    "Advertisement from %s ignored: no manufacturer data: %s",
                    self._ble_address,
                    service_info,
                )
            return
        self._process_manufacturer_data(manufacturer_data, service_info.time)

    async def _async_update_data(self) -> SwissinnoTrapData:
        """Poll for advertisements if we have not seen one recently."""
        info = async_last_service_info(self.hass, self._ble_address)
        if info and info.time != self._last_service_info_time:
            manufacturer_data = self._parse_manufacturer_data(info)
            if manufacturer_data:
                self._process_manufacturer_data(manufacturer_data, info.time)
            elif self.debug:
                _LOGGER.debug(
                    "Cached service info from %s lacked manufacturer data: %s",
                    self._ble_address,
                    info,
                )
            return self.data

        service_info = await self._async_get_advertisement(
            BluetoothScanningMode.PASSIVE, 60
        )
        if not service_info:
            if self.debug:
                _LOGGER.debug(
                    "Passive scan timed out for %s after 60s; last advertisement %s; retrying with active scan",
                    self._ble_address,
                    self.data.last_update.isoformat()
                    if self.data.last_update
                    else "never",
                )
            service_info = await self._async_get_advertisement(
                BluetoothScanningMode.ACTIVE, 10
            )
            if not service_info:
                if self.data.last_update is None:
                    raise UpdateFailed("No advertisement received")
                if self.debug and not self._missing_logged:
                    _LOGGER.debug(
                        "No advertisement received from %s since %s",
                        self._ble_address,
                        self.data.last_update.isoformat(),
                    )
                    self._missing_logged = True
                return self.data

        manufacturer_data = self._parse_manufacturer_data(service_info)
        if not manufacturer_data:
            if self.debug:
                _LOGGER.debug(
                    "Advertisement from %s lacked manufacturer data: %s",
                    self._ble_address,
                    service_info,
                )
            raise UpdateFailed("Advertisement lacked manufacturer data")
        self._process_manufacturer_data(manufacturer_data, service_info.time)
        return self.data

    def _parse_manufacturer_data(
        self, service_info: BluetoothServiceInfoBleak
    ) -> bytes | None:
        manufacturer_data = None
        for manufacturer_id in MANUFACTURER_IDS:
            data = service_info.manufacturer_data.get(manufacturer_id)
            if data:
                manufacturer_data = data
                if self.debug:
                    _LOGGER.debug(
                        "Found manufacturer data with ID 0x%04X", manufacturer_id
                    )
                break
        if not manufacturer_data and service_info.manufacturer_data:
            manufacturer_id_found, manufacturer_data = next(
                iter(service_info.manufacturer_data.items())
            )
            if self.debug:
                _LOGGER.debug(
                    "Using manufacturer data with unexpected ID 0x%04X",
                    manufacturer_id_found,
                )
        return manufacturer_data

    def _process_manufacturer_data(
        self, manufacturer_data: bytes, time: float | None
    ) -> None:
        if self.debug:
            _LOGGER.debug(
                "Manufacturer data from %s: %s",
                self._ble_address,
                manufacturer_data.hex().upper(),
            )
        self.data.raw = manufacturer_data.hex().upper()

        if len(manufacturer_data) >= 1:
            status_byte = manufacturer_data[0]
            if status_byte == 0x00:
                self.data.triggered = False
            elif status_byte == 0x01:
                self.data.triggered = True
            else:
                self.data.triggered = None
                if self.debug:
                    _LOGGER.debug("Unknown status byte 0x%02X", status_byte)

        raw = _parse_battery_raw(manufacturer_data)
        if raw is not None:
            voltage = _raw_to_voltage(raw)
            self.data.voltage = voltage
            min_v = (
                BATTERY_MIN_VOLTAGE_RECHARGEABLE
                if self.rechargeable
                else BATTERY_MIN_VOLTAGE
            )
            max_v = (
                BATTERY_MAX_VOLTAGE_RECHARGEABLE
                if self.rechargeable
                else BATTERY_MAX_VOLTAGE
            )
            self.data.battery = _voltage_to_percentage(voltage, min_v, max_v)

        if time is not None:
            self.data.last_update = dt_util.utcnow()
            self._last_service_info_time = time
            self._missing_logged = False

        self.async_set_updated_data(self.data)
        if self.debug:
            _LOGGER.debug(
                "Processed advertisement for %s: triggered=%s voltage=%s battery=%s last_update=%s",
                self._ble_address,
                self.data.triggered,
                self.data.voltage,
                self.data.battery,
                self.data.last_update,
            )

    async def async_shutdown(self) -> None:
        """Clean up callbacks."""
        if self._unsub:
            self._unsub()
            self._unsub = None

    async def _async_get_advertisement(
        self, mode: BluetoothScanningMode, timeout: int
    ) -> BluetoothServiceInfoBleak | None:
        """Wait for an advertisement that contains manufacturer data."""
        def _match(service_info: BluetoothServiceInfoBleak) -> bool:
            if service_info.address == self._ble_address and self.debug:
                _LOGGER.debug(
                    "Saw advertisement from %s (connectable=%s, has_manufacturer=%s)",
                    self._ble_address,
                    service_info.connectable,
                    bool(service_info.manufacturer_data),
                )
            return service_info.address == self._ble_address and bool(
                service_info.manufacturer_data
            )

        try:
            return await async_process_advertisements(
                self.hass,
                _match,
                self._matcher,
                mode,
                timeout,
            )
        except (asyncio.TimeoutError, asyncio.CancelledError):
            return None


def _parse_battery_raw(manufacturer_data: bytes) -> int | None:
    """Return the raw battery reading from manufacturer data."""
    if len(manufacturer_data) < 9:
        return None
    return int.from_bytes(manufacturer_data[7:9], "little")


def _raw_to_voltage(raw: int) -> float:
    """Convert the raw battery reading to volts."""
    return round((raw - 253) / 72, 2)


def _voltage_to_percentage(
    voltage: float, min_voltage: float, max_voltage: float
) -> int:
    """Convert a voltage reading to a battery percentage."""
    percent = (voltage - min_voltage) / (max_voltage - min_voltage) * 100
    return max(0, min(100, round(percent)))
