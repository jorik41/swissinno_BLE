import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.bluetooth import (
    async_register_callback,
    BluetoothServiceInfoBleak,
    BluetoothChange,
    BluetoothScanningMode,
)
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.core import callback
from homeassistant.const import CONF_NAME, CONF_MAC
from .const import DOMAIN, MANUFACTURER_IDS, UNAVAILABLE_AFTER_SECS

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    """Set up Swissinno BLE sensor based on a config entry."""
    address = config_entry.data[CONF_MAC].lower()
    name = config_entry.data[CONF_NAME]

    sensor = SwissinnoBLESensor(hass, address, name)
    async_add_entities([sensor])

class SwissinnoBLESensor(SensorEntity):
    """Representation of a Swissinno BLE sensor."""

    def __init__(self, hass, address, name):
        """Initialize the sensor."""
        self._hass = hass
        self._address = address
        self._name = f"{name} Status"
        self._state = None
        self._attr_unique_id = f"{self._address}_status"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, self._address)},
            name=name,
            manufacturer="Swissinno",
            model="Swissinno Mouse Trap",
        )
        self._unsub = None
        self._available = False
        self._last_seen = None

        # Registreer de callback
        self._unsub = async_register_callback(
            hass,
            self._async_handle_ble_event,
            {"address": self._address},
            BluetoothScanningMode.ACTIVE,
        )

    @callback
    def _async_handle_ble_event(
        self,
        service_info: BluetoothServiceInfoBleak,
        change: BluetoothChange,
    ):
        """Verwerk een Bluetooth-evenement."""
        _LOGGER.debug("Ontvangen advertentie van %s: %s", self._address, service_info)

        # Verwerk de advertentiegegevens
        manufacturer_data = None
        for manufacturer_id in MANUFACTURER_IDS:
            data = service_info.manufacturer_data.get(manufacturer_id)
            if data:
                manufacturer_data = data
                _LOGGER.debug("Gevonden manufacturer data met ID 0x%04X", manufacturer_id)
                break

        if not manufacturer_data:
            _LOGGER.debug("Geen manufacturer data met IDs %s gevonden", [f"0x{mid:04X}" for mid in MANUFACTURER_IDS])
            return

        if len(manufacturer_data) < 1:
            _LOGGER.debug("Manufacturer data is te kort")
            return

        status_byte = manufacturer_data[0]
        _LOGGER.debug("Status byte: 0x%02X", status_byte)

        if status_byte == 0x00:
            state = "Niet geactiveerd"
        elif status_byte == 0x01:
            state = "Geactiveerd"
        else:
            state = f"Onbekende status: 0x{status_byte:02X}"

        self._state = state
        self._available = True
        self._last_seen = self._hass.loop.time()
        self.async_write_ha_state()

    @property
    def name(self):
        """Geef de naam van de sensor terug."""
        return self._name

    @property
    def native_value(self):
        """Geef de huidige status terug."""
        return self._state

    @property
    def available(self):
        """Geef True terug als de sensor beschikbaar is."""
        if self._last_seen is None:
            return False
        return (self._hass.loop.time() - self._last_seen) < UNAVAILABLE_AFTER_SECS

    async def async_will_remove_from_hass(self):
        """Opschonen wanneer de entiteit wordt verwijderd."""
        if self._unsub:
            self._unsub()
            self._unsub = None