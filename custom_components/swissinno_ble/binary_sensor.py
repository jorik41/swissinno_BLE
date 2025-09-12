"""Swissinno BLE binary sensors."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import SwissinnoBLECoordinator
from .entity import SwissinnoBLEEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Swissinno BLE binary sensors based on a config entry."""
    coordinator: SwissinnoBLECoordinator = hass.data[DOMAIN][config_entry.entry_id]
    name = config_entry.data[CONF_NAME]

    async_add_entities([SwissinnoBLETriggeredSensor(coordinator, name)])


class SwissinnoBLETriggeredSensor(SwissinnoBLEEntity, BinarySensorEntity):
    """Representation of the trap triggered state."""

    _attr_device_class = BinarySensorDeviceClass.OCCUPANCY

    def __init__(self, coordinator: SwissinnoBLECoordinator, device_name: str) -> None:
        super().__init__(coordinator, device_name, "Status", "status")

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.triggered
