"""Unofficial Swissinno BLE reset button for Home Assistant.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

import inspect
import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.components.bluetooth import async_ble_device_from_address
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
        self._ble_address = address.upper()
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

    def _notify(self, message: str) -> None:
        """Show a persistent notification, scheduling if needed."""
        result = async_create_persistent_notification(
            self.hass, message, title="Mouse Trap"
        )
        if inspect.isawaitable(result):
            self.hass.async_create_task(result)

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
        import time
        from bleak import BleakClient, BleakScanner
        from bleak.exc import BleakError

        try:
            _LOGGER.debug(
                "Trying to resolve BLE device %s with connectable advertisement",
                self._ble_address,
            )
            device = async_ble_device_from_address(
                self.hass, self._ble_address, connectable=True
            )
            if not device:
                _LOGGER.debug(
                    "No connectable advertisement found for %s; retrying without connectable filter",
                    self._ble_address,
                )
                # Some devices incorrectly advertise as non-connectable; try again
                # without requiring a connectable advertisement.
                device = async_ble_device_from_address(
                    self.hass, self._ble_address, connectable=False
                )
            if not device:
                _LOGGER.debug(
                    "Bluetooth cache lookup still empty for %s; starting active scan fallback",
                    self._ble_address,
                )

                async def _scan_for_device() -> object | None:
                    """Scan for the device using Bleak."""
                    if hasattr(BleakScanner, "find_device_by_address"):
                        try:
                            return await BleakScanner.find_device_by_address(
                                self._ble_address, timeout=5.0
                            )
                        except Exception as scan_err:  # noqa: BLE001
                            _LOGGER.debug(
                                "BleakScanner.find_device_by_address failed for %s: %s",
                                self._ble_address,
                                scan_err,
                            )
                    # Manual scan loop as fallback for older bleak versions
                    scanner = BleakScanner()
                    await scanner.start()
                    try:
                        deadline = time.monotonic() + 5.0
                        while time.monotonic() < deadline:
                            devices = scanner.discovered_devices
                            for discovered in devices:
                                if discovered.address.lower() == self._address:
                                    return discovered
                            await asyncio.sleep(0.5)
                    finally:
                        await scanner.stop()
                    return None

                device = await _scan_for_device()
            if not device:
                msg = (
                    f"Bluetooth device with address {self._ble_address} not found"
                )
                _LOGGER.error(msg)
                self._notify(msg)
                return

            try:
                client_kwargs = {}
                details = getattr(device, "details", None)
                if isinstance(details, dict):
                    adapter = details.get("source") or details.get("adapter")
                    if adapter:
                        client_kwargs["adapter"] = adapter
                if client_kwargs:
                    _LOGGER.debug(
                        "Connecting to %s via adapter %s",
                        self._ble_address,
                        client_kwargs["adapter"],
                    )
                async with BleakClient(device, **client_kwargs) as client:
                    result = client.write_gatt_char(RESET_CHAR_UUID, b"\x00")
                    if inspect.isawaitable(result):
                        await result
                    _LOGGER.debug("Reset command sent to %s", self._ble_address)
                    # Give the trap a moment to process the reset command before
                    # re-enabling the button. Without this delay the reset may not
                    # take effect reliably.
                    await asyncio.sleep(1)
            except (BleakError, OSError) as err:
                msg = f"Failed to reset mouse trap {self._name}: {err}"
                _LOGGER.error(msg)
                self._notify(msg)
        finally:
            # Re-enable the button once the reset has completed or failed.
            self._attr_available = True
            self.async_write_ha_state()
