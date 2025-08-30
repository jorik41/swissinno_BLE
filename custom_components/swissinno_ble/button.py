import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.persistent_notification import (
    async_create as async_create_persistent_notification,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, RESET_CHAR_UUID

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
            manufacturer="Swissinno",
            model="Swissinno Mouse Trap",
        )

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
        try:
            from bleak import BleakClient

            client = BleakClient(self._address)
            try:
                await client.connect()
                await client.write_gatt_char(RESET_CHAR_UUID, b"\x00")
                _LOGGER.debug("Reset command sent to %s", self._address)
            finally:
                await client.disconnect()

        except Exception as err:
            _LOGGER.error("Error resetting the mouse trap: %s", err)
            await async_create_persistent_notification(
                self.hass,
                f"Error resetting mouse trap {self._name}: {err}",
                title="Swissinno Mouse Trap",
            )

