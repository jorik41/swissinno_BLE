"""Swissinno BLE sensors."""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime

from homeassistant.components import mqtt
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
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util
from homeassistant.components.mqtt.models import ReceiveMessage

from .const import DOMAIN
from .coordinator import SwissinnoBLECoordinator
from .entity import SwissinnoBLEEntity


_LOGGER = logging.getLogger(__name__)

OUTPUT_SENSORS: tuple[tuple[str, str, str], ...] = (
    (
        "Oracle Last Prediction",
        "oracle_last_prediction",
        "trinitygrid/oracle/prediction",
    ),
    (
        "General Last Decision",
        "general_last_decision",
        "trinitygrid/general/decision",
    ),
    (
        "Justice Last Report",
        "justice_last_report",
        "trinitygrid/justice/report",
    ),
)


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

    sensors.extend(
        SwissinnoBLEAgentOutputSensor(
            hass,
            coordinator,
            name,
            sensor_name,
            unique_suffix,
            topic,
        )
        for sensor_name, unique_suffix, topic in OUTPUT_SENSORS
    )
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


class SwissinnoBLEAgentOutputSensor(SensorEntity):
    """Sensor that exposes the latest agent output published via MQTT."""

    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        coordinator: SwissinnoBLECoordinator,
        device_name: str,
        name: str,
        unique_suffix: str,
        topic: str,
    ) -> None:
        self.hass = hass
        self._topic = topic
        self._unsubscribe: Callable[[], None] | None = None
        self._available = False
        self._attr_name = name
        self._attr_native_value: str | None = None
        self._attr_unique_id = f"{coordinator.address}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=device_name,
            manufacturer="Swissinno (unofficial)",
            model="Mouse Trap",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        try:
            await mqtt.async_wait_for_mqtt_client(self.hass)
        except HomeAssistantError as err:
            _LOGGER.error(
                "Unable to subscribe to %s because MQTT client is not available: %s",
                self._topic,
                err,
            )
            self._available = False
            self.async_write_ha_state()
            return

        self._unsubscribe = await mqtt.async_subscribe(
            self.hass,
            self._topic,
            self._message_received,
        )
        self._available = True
        self.async_write_ha_state()

    async def async_will_remove_from_hass(self) -> None:
        await super().async_will_remove_from_hass()
        if self._unsubscribe:
            self._unsubscribe()
            self._unsubscribe = None

    @callback
    def _message_received(self, message: ReceiveMessage) -> None:
        self._attr_native_value = message.payload
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return self._available

