"""Unofficial Swissinno BLE integration for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.const import Platform

from .const import DOMAIN, LOG_FILE

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BUTTON]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Swissinno BLE component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Swissinno BLE from a config entry."""
    if entry.options.get("debug_logging"):
        logger = logging.getLogger(__package__)
        logger.setLevel(logging.DEBUG)
        log_file = hass.config.path(LOG_FILE)
        if not any(
            isinstance(h, logging.FileHandler) and h.baseFilename == log_file
            for h in logger.handlers
        ):
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(
                logging.Formatter(
                    "%(asctime)s %(name)s %(levelname)s: %(message)s"
                )
            )
            logger.addHandler(file_handler)
        logger.propagate = False

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Swissinno BLE config entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if entry.options.get("debug_logging"):
        logger = logging.getLogger(__package__)
        log_file = hass.config.path(LOG_FILE)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == log_file:
                logger.removeHandler(handler)
                handler.close()
        logger.propagate = True
        logger.setLevel(logging.INFO)

    return result

