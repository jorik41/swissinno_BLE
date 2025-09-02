"""Unofficial Swissinno BLE sensors for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

from __future__ import annotations

import logging

from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
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
    sensors = [
        SwissinnoBLEStatusSensor(hass, address, name),
        SwissinnoBLEVoltageSensor(hass, address, name),
        SwissinnoBLEBatterySensor(hass, address, name, rechargeable),
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
                BluetoothCallbackMatcher(manufacturer_id=manufacturer_id),
                BluetoothScanningMode.ACTIVE,
            )
            for manufacturer_id in MANUFACTURER_IDS
        ]
        self._last_seen: float | None = self._hass.loop.time()

    @callback
    def _async_handle_ble_event(
        self, service_info: BluetoothServiceInfoBleak, change: BluetoothChange
    ) -> None:
        """Process a Bluetooth event."""
        _LOGGER.debug("Advertisement from %s: %s", service_info.address, service_info)

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


class SwissinnoBLEStatusSensor(SwissinnoBLEEntity):
    """Representation of the trap status."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        super().__init__(hass, address, name, "Status", "status")
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

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        super().__init__(hass, address, name, "Battery Voltage", "voltage")
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
    ) -> None:
        super().__init__(hass, address, name, "Battery", "battery")
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._percentage: int | None = None
        self._rechargeable = rechargeable

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

