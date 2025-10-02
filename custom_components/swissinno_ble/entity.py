"""Base entity class for Swissinno BLE integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, UNAVAILABLE_AFTER_SECS
from .coordinator import SwissinnoBLECoordinator, SwissinnoTrapData


class SwissinnoBLEEntity(CoordinatorEntity[SwissinnoBLECoordinator]):
    """Base class for Swissinno BLE entities."""

    def __init__(
        self,
        coordinator: SwissinnoBLECoordinator,
        device_name: str,
        name_suffix: str,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._attr_name = f"{device_name} {name_suffix}"
        self._attr_unique_id = f"{coordinator.address}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.address)},
            name=device_name,
            manufacturer="Swissinno (unofficial)",
            model="Mouse Trap",
        )

    @property
    def available(self) -> bool:
        """Return True if the entity is available."""
        last_update = self.coordinator.data.last_update
        if last_update is None:
            return False
        return (dt_util.utcnow() - last_update) < timedelta(
            seconds=UNAVAILABLE_AFTER_SECS
        )
