# OUPES Mega 2 for Home Assistant

Custom Home Assistant integration for monitoring an OUPES Mega 2 power station over the local network.

## Features

- Battery percentage, voltage, and temperature sensors
- AC, solar, and total input power sensors
- AC output power sensor
- Time remaining sensor
- Charge mode sensor
- AC output and DC output binary sensors

## Setup

1. Copy `custom_components/oupes_mega2` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from the UI.
4. Enter the device IP address, TCP port, device ID, and device key from the OUPES app.
5. Close the OUPES mobile app while Home Assistant is polling the device.

## Notes

- This integration uses local TCP polling and does not rely on a cloud service.
- The published source does not include any device-specific credentials or Home Assistant storage data.

## Repository

- Issues: <https://github.com/ryanbytes/ha-oupes-mega2/issues>
- Source: <https://github.com/ryanbytes/ha-oupes-mega2>
