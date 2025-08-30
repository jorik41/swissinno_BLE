import re

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.device_registry import format_mac

from .const import DOMAIN

class SwissinnoBLEConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Swissinno BLE."""

    VERSION = 1

    def __init__(self) -> None:
        self._discovery_info: BluetoothServiceInfoBleak | None = None

    async def async_step_user(self, user_input=None):
        """Handle the initial step."""
        errors: dict[str, str] = {}
        if user_input is not None:
            mac_address = format_mac(user_input[CONF_MAC])
            name = user_input[CONF_NAME]

            if not self._valid_mac(mac_address):
                errors["base"] = "invalid_mac"
            else:
                await self.async_set_unique_id(mac_address)
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_MAC: mac_address,
                        CONF_NAME: name,
                    },
                )

        data_schema = vol.Schema(
            {
                vol.Required(
                    CONF_NAME,
                    default=(self._discovery_info.name if self._discovery_info else "Swissinno Mouse Trap"),
                ): str,
                vol.Required(
                    CONF_MAC,
                    default=(
                        format_mac(self._discovery_info.address)
                        if self._discovery_info
                        else ""
                    ),
                ): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak):
        """Handle a bluetooth discovery flow."""
        await self.async_set_unique_id(format_mac(discovery_info.address), raise_on_progress=False)
        self._abort_if_unique_id_configured()
        self._discovery_info = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.name or "Swissinno Mouse Trap"}
        return await self.async_step_user()

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return SwissinnoBLEOptionsFlow(config_entry)

    def _valid_mac(self, mac: str) -> bool:
        """Validate the MAC address format."""
        pattern = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
        return pattern.match(mac) is not None

class SwissinnoBLEOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Swissinno BLE."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        return await self.async_step_user()

    async def async_step_user(self, user_input=None):
        """Handle the options step."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema(
            {
                vol.Optional("update_interval", default=60): vol.All(
                    vol.Coerce(int), vol.Range(min=30)
                )
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema)

