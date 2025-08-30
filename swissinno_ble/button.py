# custom_components/swissinno_ble/button.py

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN, SERVICE_UUID

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
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
        self._state = None

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
            async with BleakClient(self._address) as client:
                # Zorg ervoor dat de GATT-service beschikbaar is
                services = await client.get_services()
                if SERVICE_UUID not in services:
                    _LOGGER.error("SERVICE_UUID %s niet gevonden op %s", SERVICE_UUID, self._address)
                    self.hass.components.persistent_notification.create(
                        f"SERVICE_UUID {SERVICE_UUID} niet gevonden op {self._address}",
                        title="Swissinno Mouse Trap",
                    )
                    return

                await client.write_gatt_char(SERVICE_UUID, b'\x00')
                _LOGGER.debug("Reset command sent to %s", self._address)
                # Optioneel: Update de sensorstatus na reset
                # Dit gebeurt automatisch door de advertentie callback
        except Exception as e:
            _LOGGER.error("Error resetting the mouse trap: %s", e)
            self.hass.components.persistent_notification.create(
                f"Error resetting mouse trap {self._name}: {e}",
                title="Swissinno Mouse Trap",
            )
