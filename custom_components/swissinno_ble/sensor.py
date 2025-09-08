"""Unofficial Swissinno BLE sensors for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta

from homeassistant.util import dt as dt_util

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_process_advertisements,
    async_register_callback,
)
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_MAC,
    CONF_NAME,
    PERCENTAGE,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
    BATTERY_MAX_VOLTAGE,
    BATTERY_MAX_VOLTAGE_RECHARGEABLE,
    BATTERY_MIN_VOLTAGE,
    BATTERY_MIN_VOLTAGE_RECHARGEABLE,
    DOMAIN,
    MANUFACTURER_IDS,
    UNAVAILABLE_AFTER_SECS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Swissinno BLE sensors based on a config entry."""
    address = config_entry.data[CONF_MAC].lower()
    name = config_entry.data[CONF_NAME]

    rechargeable = config_entry.options.get("rechargeable_battery", False)
    update_interval = config_entry.options.get("update_interval", 60)
    sensors = [
        SwissinnoBLEStatusSensor(hass, address, name, update_interval),
        SwissinnoBLEVoltageSensor(hass, address, name, update_interval),
        SwissinnoBLEBatterySensor(hass, address, name, rechargeable, update_interval),
        SwissinnoBLELastUpdateSensor(hass, address, name, update_interval),
        SwissinnoBLERawBeaconSensor(hass, address, name, update_interval),
    ]
    async_add_entities(sensors)


def _parse_battery_raw(manufacturer_data: bytes) -> int | None:
    """Return the raw battery reading from manufacturer data."""
    if len(manufacturer_data) < 9:
        return None
    return int.from_bytes(manufacturer_data[7:9], "little")


def _raw_to_voltage(raw: int) -> float:
    """Convert the raw battery reading to volts."""
    return round((raw - 253) / 72, 2)


def _voltage_to_percentage(voltage: float, min_voltage: float, max_voltage: float) -> int:
    """Convert a voltage reading to a battery percentage."""
    percent = (voltage - min_voltage) / (max_voltage - min_voltage) * 100
    return max(0, min(100, round(percent)))


class SwissinnoBLEEntity(SensorEntity):
    """Base class for Swissinno BLE entities."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        name_suffix: str,
        unique_suffix: str,
        update_interval: int,
    ) -> None:
        self._hass = hass
        self._address = address
        self._name = f"{name} {name_suffix}"
        self._attr_should_poll = False
        self._attr_unique_id = f"{self._address}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=name,
            manufacturer="Swissinno (unofficial)",
            model="Mouse Trap",
        )
        self._unsub = [
            async_register_callback(
                hass,
                self._async_handle_ble_event,
                BluetoothCallbackMatcher(
                    manufacturer_id=manufacturer_id,
                ),
                BluetoothScanningMode.ACTIVE,
            )
            for manufacturer_id in MANUFACTURER_IDS
        ]
        self._last_seen: float | None = self._hass.loop.time()
        self._last_seen_datetime: datetime | None = dt_util.utcnow()
        self._update_interval = timedelta(seconds=update_interval)
        self._unsub_interval = None

    @callback
    def _async_handle_ble_event(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Process a Bluetooth event."""
        _LOGGER.debug("Advertisement from %s: %s", service_info.address, service_info)

        # Ignore advertisements from other devices; the matcher subscribes
        # based solely on manufacturer ID
        if service_info.address.lower() != self._address:
            return

        manufacturer_data = None
        for manufacturer_id in MANUFACTURER_IDS:
            data = service_info.manufacturer_data.get(manufacturer_id)
            if data:
                manufacturer_data = data
                _LOGGER.debug(
                    "Found manufacturer data with ID 0x%04X", manufacturer_id
                )
                break

        if not manufacturer_data:
            _LOGGER.debug(
                "No manufacturer data with IDs %s found",
                [f"0x{mid:04X}" for mid in MANUFACTURER_IDS],
            )
            return

        self._handle_data(manufacturer_data)
        self._last_seen = self._hass.loop.time()
        self._last_seen_datetime = dt_util.utcnow()
        if self.hass is None:
            _LOGGER.debug(
                "Entity not yet added to Home Assistant; skipping state update"
            )
            return
        self.async_write_ha_state()

    def _handle_data(self, manufacturer_data: bytes) -> None:
        """Handle manufacturer data."""

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        if self._last_seen is None:
            return False
        return (self._hass.loop.time() - self._last_seen) < UNAVAILABLE_AFTER_SECS

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when the entity is removed."""
        if self._unsub:
            for unsub in self._unsub:
                unsub()
            self._unsub = None
        if self._unsub_interval:
            self._unsub_interval()
            self._unsub_interval = None

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""
        await super().async_added_to_hass()

        async def _refresh(now):
            await self._async_request_update()

        self._unsub_interval = async_track_time_interval(
            self._hass, _refresh, self._update_interval
        )
        self._hass.async_create_task(self._async_request_update())

    async def _async_request_update(self) -> None:
        """Request an advertisement and process the data."""
        for manufacturer_id in MANUFACTURER_IDS:
            try:
                service_info = await async_process_advertisements(
                    self._hass,
                    lambda si: si.address.lower() == self._address
                    and bool(si.manufacturer_data.get(manufacturer_id)),
                    BluetoothCallbackMatcher(
                        address=self._address, manufacturer_id=manufacturer_id
                    ),
                    BluetoothScanningMode.ACTIVE,
                    15,
                )
            except asyncio.TimeoutError:
                _LOGGER.debug(
                    "No advertisement received for manufacturer ID 0x%04X",
                    manufacturer_id,
                )
                continue
            manufacturer_data = service_info.manufacturer_data.get(manufacturer_id)
            if not manufacturer_data:
                _LOGGER.debug(
                    "Advertisement for manufacturer ID 0x%04X lacked data",
                    manufacturer_id,
                )
                continue
            self._handle_data(manufacturer_data)
            self._last_seen = self._hass.loop.time()
            self._last_seen_datetime = dt_util.utcnow()
            if self.hass is not None:
                self.async_write_ha_state()


class SwissinnoBLEStatusSensor(SwissinnoBLEEntity):
    """Representation of the trap status."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, update_interval: int
    ) -> None:
        super().__init__(hass, address, name, "Status", "status", update_interval)
        self._state: str | None = "Not triggered"

    def _handle_data(self, manufacturer_data: bytes) -> None:
        if len(manufacturer_data) < 1:
            _LOGGER.debug("Manufacturer data is too short")
            return

        status_byte = manufacturer_data[0]
        _LOGGER.debug("Status byte: 0x%02X", status_byte)

        if status_byte == 0x00:
            self._state = "Not triggered"
        elif status_byte == 0x01:
            self._state = "Triggered"
        else:
            self._state = f"Unknown status: 0x{status_byte:02X}"

    @property
    def native_value(self) -> str | None:
        return self._state


class SwissinnoBLEVoltageSensor(SwissinnoBLEEntity):
    """Representation of the trap battery voltage."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, update_interval: int
    ) -> None:
        super().__init__(
            hass, address, name, "Battery Voltage", "voltage", update_interval
        )
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 2
        self._voltage: float | None = None

    def _handle_data(self, manufacturer_data: bytes) -> None:
        raw = _parse_battery_raw(manufacturer_data)
        if raw is None:
            _LOGGER.debug("Manufacturer data is too short")
            return
        self._voltage = _raw_to_voltage(raw)
        _LOGGER.debug("Battery raw %s -> %.2f V", raw, self._voltage)

    @property
    def native_value(self) -> float | None:
        return self._voltage


class SwissinnoBLEBatterySensor(SwissinnoBLEEntity):
    """Representation of the trap battery percentage."""

    def __init__(
        self,
        hass: HomeAssistant,
        address: str,
        name: str,
        rechargeable: bool,
        update_interval: int,
    ) -> None:
        self._rechargeable = rechargeable
        self._percentage: int | None = None
        super().__init__(hass, address, name, "Battery", "battery", update_interval)
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    def _handle_data(self, manufacturer_data: bytes) -> None:
        raw = _parse_battery_raw(manufacturer_data)
        if raw is None:
            _LOGGER.debug("Manufacturer data is too short")
            return
        voltage = _raw_to_voltage(raw)
        min_v = (
            BATTERY_MIN_VOLTAGE_RECHARGEABLE
            if self._rechargeable
            else BATTERY_MIN_VOLTAGE
        )
        max_v = (
            BATTERY_MAX_VOLTAGE_RECHARGEABLE
            if self._rechargeable
            else BATTERY_MAX_VOLTAGE
        )
        self._percentage = _voltage_to_percentage(voltage, min_v, max_v)
        _LOGGER.debug(
            "Battery raw %s -> %.2f V -> %d%%", raw, voltage, self._percentage
        )

    @property
    def native_value(self) -> int | None:
        return self._percentage


class SwissinnoBLERawBeaconSensor(SwissinnoBLEEntity):
    """Representation of the raw beacon data."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, update_interval: int
    ) -> None:
        super().__init__(hass, address, name, "Raw Beacon", "raw_beacon", update_interval)
        self._attr_entity_registry_enabled_default = False
        self._raw: str | None = None

    def _handle_data(self, manufacturer_data: bytes) -> None:
        self._raw = manufacturer_data.hex().upper()

    @property
    def native_value(self) -> str | None:
        return self._raw


class SwissinnoBLELastUpdateSensor(SwissinnoBLEEntity):
    """Representation of the last update time."""

    def __init__(
        self, hass: HomeAssistant, address: str, name: str, update_interval: int
    ) -> None:
        super().__init__(hass, address, name, "Last Update", "last_update", update_interval)
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    def _handle_data(self, manufacturer_data: bytes) -> None:
        """No additional data processing required."""

    @property
    def native_value(self) -> datetime | None:
        return self._last_seen_datetime

