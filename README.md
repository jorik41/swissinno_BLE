# Swissinno BLE (Unofficial)

![Project Logo](images/project.svg)

**Disclaimer:** This is a hobby project and is not affiliated with, endorsed by,
or supported by Swissinno AG. Swissinno is a trademark of its respective owner,
and the name is used here solely for identification purposes. No guarantees or
warranties are provided.

Home Assistant integration for Swissinno Bluetooth mouse traps. The integration
listens for Bluetooth advertisements to monitor the trap status and battery and
provides a button to remotely reset the trap.

## Features

- Automatic discovery of nearby traps via Bluetooth
- Option to manually add a trap by name and MAC address
- Monitors trap state and rechargeable battery level
- Reset button for supported traps

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS.
2. Install the **Swissinno BLE (Unofficial)** integration from HACS.
3. Restart Home Assistant.

### Manual

1. Copy the `custom_components/swissinno_ble` directory to your Home Assistant
   `custom_components` folder.
2. Restart Home Assistant.

## Configuration

1. In Home Assistant go to **Settings → Devices & services**.
2. If a supported trap is nearby, Home Assistant will offer to set it up
   automatically.
3. To add a trap manually, click **Add Integration**, search for "Swissinno BLE
   (Unofficial)" and enter the name and MAC address.

## Battery

The traps include a built-in rechargeable battery. The integration exposes
sensors for both battery voltage and an estimated charge percentage so you can
easily see when it's time to recharge.

## Notes

- Requires Bluetooth support on the host running Home Assistant.
- Tested with `bleak` version `0.20.2` or later.

