"""Unofficial Swissinno BLE integration for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

import logging

from homeassistant.exceptions import ConfigEntryNotReady

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, LOG_FILE
from .coordinator import SwissinnoBLECoordinator

PLATFORMS: list[Platform] = [Platform.BINARY_SENSOR, Platform.SENSOR, Platform.BUTTON]


logger = logging.getLogger(__package__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Swissinno BLE component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Swissinno BLE from a config entry."""
    debug_logging = entry.options.get("debug_logging", False)
    if debug_logging:
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

    address = entry.data[CONF_MAC].lower()
    rechargeable = entry.options.get("rechargeable_battery", False)
    update_interval = entry.options.get("update_interval", 60)

    coordinator = SwissinnoBLECoordinator(
        hass, address, rechargeable, debug_logging, update_interval
    )
    try:
        await coordinator.async_config_entry_first_refresh()
    except ConfigEntryNotReady:
        logger.warning(
            "No initial advertisement received from %s; entities will be unavailable until data is received",
            address,
        )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Swissinno BLE config entry."""
    result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    coordinator = hass.data[DOMAIN].pop(entry.entry_id, None)
    if coordinator:
        await coordinator.async_shutdown()

    if entry.options.get("debug_logging"):
        log_file = hass.config.path(LOG_FILE)
        for handler in list(logger.handlers):
            if isinstance(handler, logging.FileHandler) and handler.baseFilename == log_file:
                logger.removeHandler(handler)
                handler.close()
        logger.propagate = True
        logger.setLevel(logging.INFO)

    return result

