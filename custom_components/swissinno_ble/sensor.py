"""Swissinno BLE sensors."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME,
    PERCENTAGE,
    UnitOfElectricPotential,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import DOMAIN
from .coordinator import SwissinnoBLECoordinator
from .entity import SwissinnoBLEEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Swissinno BLE sensors based on a config entry."""
    coordinator: SwissinnoBLECoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    sensors = [
        SwissinnoBLEVoltageSensor(coordinator, name),
        SwissinnoBLEBatterySensor(coordinator, name),
        SwissinnoBLELastUpdateSensor(coordinator, name),
        SwissinnoBLERawBeaconSensor(coordinator, name),
    ]
    async_add_entities(sensors)


class SwissinnoBLEVoltageSensor(SwissinnoBLEEntity, SensorEntity):
    """Representation of the trap battery voltage."""

    def __init__(self, coordinator: SwissinnoBLECoordinator, device_name: str) -> None:
        super().__init__(coordinator, device_name, "Battery Voltage", "voltage")
        self._attr_device_class = SensorDeviceClass.VOLTAGE
        self._attr_native_unit_of_measurement = UnitOfElectricPotential.VOLT
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_suggested_display_precision = 2

    @property
    def native_value(self) -> float | None:
        return self.coordinator.data.voltage


class SwissinnoBLEBatterySensor(SwissinnoBLEEntity, SensorEntity):
    """Representation of the trap battery percentage."""

    def __init__(self, coordinator: SwissinnoBLECoordinator, device_name: str) -> None:
        super().__init__(coordinator, device_name, "Battery", "battery")
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.battery


class SwissinnoBLERawBeaconSensor(SwissinnoBLEEntity, SensorEntity):
    """Representation of the raw beacon data."""

    def __init__(self, coordinator: SwissinnoBLECoordinator, device_name: str) -> None:
        super().__init__(coordinator, device_name, "Raw Beacon", "raw_beacon")
        self._attr_entity_registry_enabled_default = False

    @property
    def native_value(self) -> str | None:
        return self.coordinator.data.raw


class SwissinnoBLELastUpdateSensor(SwissinnoBLEEntity, SensorEntity):
    """Representation of the last update time."""

    def __init__(self, coordinator: SwissinnoBLECoordinator, device_name: str) -> None:
        super().__init__(coordinator, device_name, "Last Update", "last_update")
        self._attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self) -> datetime | None:  # type: ignore[override]
        return self.coordinator.data.last_update

