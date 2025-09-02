import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.bluetooth import (
    BluetoothCallbackMatcher,
    BluetoothChange,
    BluetoothScanningMode,
    BluetoothServiceInfoBleak,
    async_register_callback,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_MAC, CONF_NAME
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, MANUFACTURER_IDS, UNAVAILABLE_AFTER_SECS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Swissinno BLE sensor based on a config entry."""
    address = config_entry.data[CONF_MAC].lower()
    name = config_entry.data[CONF_NAME]

    sensor = SwissinnoBLESensor(hass, address, name)
    async_add_entities([sensor])

class SwissinnoBLESensor(SensorEntity):
    """Representation of a Swissinno BLE sensor."""

    def __init__(self, hass: HomeAssistant, address: str, name: str) -> None:
        """Initialize the sensor."""
        self._hass = hass
        self._address = address
        self._name = f"{name} Status"
        self._state: str | None = "Not triggered"
        self._attr_should_poll = False
        self._attr_unique_id = f"{self._address}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=name,
            manufacturer="Swissinno",
            model="Swissinno Mouse Trap",
        )
        # Devices rotate their Bluetooth addresses for privacy which would make
        # an address based filter miss advertisements. Instead we match on the
        # manufacturer ID which remains constant for our traps and provides a
        # stable way to identify them.
        self._unsub = [
            async_register_callback(
                hass,
                self._async_handle_ble_event,
                BluetoothCallbackMatcher(manufacturer_id=manufacturer_id),
                BluetoothScanningMode.ACTIVE,
            )
            for manufacturer_id in MANUFACTURER_IDS
        ]
        self._last_seen: float | None = self._hass.loop.time()

    @callback
    def _async_handle_ble_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ) -> None:
        """Process a Bluetooth event."""
        _LOGGER.debug("Advertisement from %s: %s", service_info.address, service_info)

        manufacturer_data = None
        for manufacturer_id in MANUFACTURER_IDS:
            data = service_info.manufacturer_data.get(manufacturer_id)
            if data:
                manufacturer_data = data
                _LOGGER.debug(
                    "Found manufacturer data with ID 0x%04X", manufacturer_id
                )
                break

        # Even though the callback was registered with a manufacturer filter,
        # verify the manufacturer data to avoid processing packets from
        # unrelated devices.
        if not manufacturer_data:
            _LOGGER.debug(
                "No manufacturer data with IDs %s found",
                [f"0x{mid:04X}" for mid in MANUFACTURER_IDS],
            )
            return

        if len(manufacturer_data) < 1:
            _LOGGER.debug("Manufacturer data is too short")
            return

        status_byte = manufacturer_data[0]
        _LOGGER.debug("Status byte: 0x%02X", status_byte)

        if status_byte == 0x00:
            state = "Not triggered"
        elif status_byte == 0x01:
            state = "Triggered"
        else:
            state = f"Unknown status: 0x{status_byte:02X}"

        self._state = state
        self._last_seen = self._hass.loop.time()
        self.async_write_ha_state()

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> str | None:
        """Return the current status."""
        return self._state

    @property
    def available(self) -> bool:
        """Return True if the sensor is available."""
        if self._last_seen is None:
            return False
        return (self._hass.loop.time() - self._last_seen) < UNAVAILABLE_AFTER_SECS

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when the entity is removed."""
        if self._unsub:
            for unsub in self._unsub:
                unsub()
            self._unsub = None

