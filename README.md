# Swissinno BLE

Home Assistant integration for [Swissinno](https://www.swissinno.com/) Bluetooth
mouse traps. The integration listens for Bluetooth advertisements to monitor the
trap status and provides a button to remotely reset the trap.

## Features

- Detects trap state via Bluetooth manufacturer data
- Reset button for supported traps
- Config flow for easy setup

## Installation

### HACS (recommended)

1. Add this repository as a custom repository in HACS.
2. Install the **Swissinno BLE** integration from HACS.
3. Restart Home Assistant.

### Manual

1. Copy the `custom_components/swissinno_ble` directory to your Home Assistant
   `custom_components` folder.
2. Restart Home Assistant.

## Configuration

1. In Home Assistant go to **Settings → Devices & services**.
2. Click **Add Integration** and search for "Swissinno BLE".
3. Enter the name and MAC address of your trap.

## BLE details

- The first byte of the Swissinno manufacturer data is `0x00` when the trap is
  not triggered and `0x01` when triggered.
- Resetting the trap is done by writing `0x00` to characteristic
  `02ecc6cd-2b43-4db5-96e6-ede92cf8778d` (`0x01` indicates a triggered state).
- The trap name can be read and written via characteristic
  `02ecc6cd-2b43-4db5-96e6-ede92cf8778b`.

## Notes

- Requires Bluetooth support on the host running Home Assistant.
- Tested with `bleak` version `0.20.2` or later.

