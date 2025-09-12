# Swissinno BLE (Unofficial)

![Project Logo](images/project.svg)

**Disclaimer:** This is a hobby project and is not affiliated with, endorsed by,
or supported by Swissinno AG. Swissinno is a trademark of its respective owner,
and the name is used here solely for identification purposes. No guarantees or
warranties are provided.

Home Assistant integration for Swissinno Bluetooth mouse traps. The integration
listens for Bluetooth advertisements to monitor the trap status and provides a
button to remotely reset the trap.

## Features

- Triggered state exposed as a binary sensor
- Battery voltage and percentage sensors
- Reset button for supported traps
- Config flow for easy setup
- "Last Update" sensor showing when data was last received
- Optional detailed debug logging for troubleshooting (written to `swissinno_ble.log`)

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
2. Click **Add Integration** and search for "Swissinno BLE (Unofficial)".
3. Enter the name and MAC address of your trap (case-insensitive).
4. Enable **Debug logging** in the integration options if you need detailed
   information about received Bluetooth data. Logs are written to
   `swissinno_ble.log` in your Home Assistant configuration directory.

## BLE details

- The first byte of the Swissinno manufacturer data is `0x00` when the trap is
  not triggered and `0x01` when triggered.
- Resetting the trap is done by writing `0x00` to characteristic
  `02ecc6cd-2b43-4db5-96e6-ede92cf8778d` (`0x01` indicates a triggered state).
- The trap name can be read and written via characteristic
  `02ecc6cd-2b43-4db5-96e6-ede92cf8778b`.
- Manufacturer data also contains the trap's battery voltage. Examples:
  - `0x0201060303D6FC0DFFBB0B001AAC12030001B80100` → 2.6 V
  - `0x0201060303D6FC0DFFBB0B001DAC12030001CA0100` → 2.85 V
  - `0x0201060303D6FC0DFFBB0B001FAC12030001DA0100` → 3.08 V
  - Bytes 7–8 (zero-indexed) of the manufacturer data form a little-endian
    value used to calculate the battery voltage via `(raw - 253) / 72`. The
    integration exposes **Battery Voltage** and **Battery** sensors which show
    the voltage and an approximate percentage (2.0 V empty, 3.2 V full).

## Notes

- Requires Bluetooth support on the host running Home Assistant.
- Tested with `bleak` version `0.20.2` or later.

