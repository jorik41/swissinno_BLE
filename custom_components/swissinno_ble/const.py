"""Constants for the unofficial Swissinno BLE integration.

This hobby project is not affiliated with Swissinno AG and is provided without
any guarantees. Swissinno is a trademark of its respective owner.
"""

DOMAIN = "swissinno_ble"

# Manufacturer IDs for Swissinno devices
MANUFACTURER_IDS = [0xBB0B, 0x0BBB]

# Time in seconds after which the sensor is marked as unavailable
UNAVAILABLE_AFTER_SECS = 600  # 10 minutes

# Battery voltage range used for percentage calculation
BATTERY_MIN_VOLTAGE = 2.0
BATTERY_MAX_VOLTAGE = 3.2

# GATT characteristic holding the trap name
NAME_CHAR_UUID = "02ecc6cd-2b43-4db5-96e6-ede92cf8778b"

# GATT characteristic used to reset the trap
# Write 0x00 to mark the trap as not triggered (0x01 means triggered)
RESET_CHAR_UUID = "02ecc6cd-2b43-4db5-96e6-ede92cf8778d"

