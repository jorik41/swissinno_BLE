"""Unofficial Swissinno BLE reset button for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothScanningMode,
    async_ble_device_from_address,
    async_process_advertisements,
)
from homeassistant.components.persistent_notification import (
    async_create as async_create_persistent_notification,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER_IDS, RESET_CHAR_UUID

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Swissinno BLE reset button based on a config entry."""
    name = entry.data[CONF_NAME]
    address = entry.data[CONF_MAC]

    button = SwissinnoResetButton(name, address)
    async_add_entities([button])


class SwissinnoResetButton(ButtonEntity):
    """Representation of the Swissinno BLE reset button."""

    def __init__(self, name, address):
        """Initialize the button."""
        self._name = f"{name} Reset"
        self._address = address.lower()
        self._attr_unique_id = f"{self._address}_reset_button"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=name,
            manufacturer="Swissinno (unofficial)",
            model="Mouse Trap",
        )
        # Mark the button as available by default. It will be temporarily
        # disabled while a reset is in progress to provide user feedback.
        self._attr_available = True

    @property
    def name(self):
        """Return the name of the button."""
        return self._name

    @property
    def icon(self):
        """Return the icon to use in the frontend."""
        return "mdi:restart"

    async def async_press(self):
        """Handle the button press."""
        # Avoid multiple concurrent reset attempts.
        if not self._attr_available:
            return

        # Disable the button in the frontend to provide feedback that the
        # request is being processed.
        self._attr_available = False
        self.async_write_ha_state()

        import asyncio
        from bleak import BleakClient
        from bleak.exc import BleakError

        try:
            device = async_ble_device_from_address(
                self.hass, self._address, connectable=True
            )
            if not device:
                _LOGGER.debug(
                    "Device %s not found in cache, attempting rediscovery", self._address
                )
                for manufacturer_id in MANUFACTURER_IDS:
                    _LOGGER.debug(
                        "Scanning for manufacturer ID 0x%04X", manufacturer_id
                    )
                    try:
                        service_info = await async_process_advertisements(
                            self.hass,
                            lambda _: True,
                            BluetoothCallbackMatcher(manufacturer_id=manufacturer_id),
                            BluetoothScanningMode.ACTIVE,
                            15,
                        )
                    except asyncio.TimeoutError:
                        _LOGGER.debug(
                            "No advertisement received for manufacturer ID 0x%04X",
                            manufacturer_id,
                        )
                        continue
                    manufacturer_data = service_info.manufacturer_data.get(
                        manufacturer_id
                    )
                    if not manufacturer_data:
                        _LOGGER.debug(
                            "Advertisement for manufacturer ID 0x%04X lacked data",
                            manufacturer_id,
                        )
                        continue
                    device = service_info.device
                    self._address = device.address.lower()
                    _LOGGER.debug(
                        "Rediscovered device with address %s via manufacturer ID 0x%04X",
                        self._address,
                        manufacturer_id,
                    )
                    break

            if not device:
                msg = (
                    f"Bluetooth device with address {self._address} not found and"
                    " rediscovery by manufacturer ID failed"
                )
                _LOGGER.error(msg)
                await async_create_persistent_notification(
                    self.hass, msg, title="Mouse Trap"
                )
                return

            try:
                async with BleakClient(device) as client:
                    await client.write_gatt_char(RESET_CHAR_UUID, b"\x00")
                    _LOGGER.debug("Reset command sent to %s", self._address)
            except (BleakError, OSError) as err:
                msg = f"Failed to reset mouse trap {self._name}: {err}"
                _LOGGER.error(msg)
                await async_create_persistent_notification(
                    self.hass, msg, title="Mouse Trap"
                )
        finally:
            # Re-enable the button once the reset has completed or failed.
            self._attr_available = True
            self.async_write_ha_state()
