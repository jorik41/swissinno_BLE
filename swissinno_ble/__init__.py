# custom_components/swissinno_ble/__init__.py

"""Swissinno BLE integration."""

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the Swissinno BLE component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up Swissinno BLE from a config entry."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload Swissinno BLE config entry."""
    return True