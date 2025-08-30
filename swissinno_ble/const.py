# custom_components/swissinno_ble/const.py

DOMAIN = "swissinno_ble"

# Manufacturer IDs voor Swissinno apparaten
MANUFACTURER_IDS = [0xBB0B, 0x0BBB]

# Tijd in seconden waarna de sensor als 'niet beschikbaar' wordt gemarkeerd
UNAVAILABLE_AFTER_SECS = 600  # 10 minuten