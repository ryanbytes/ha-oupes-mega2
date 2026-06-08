# OUPES Mega 2 for Home Assistant

Custom Home Assistant integration for monitoring an **OUPES Mega 2** power station over the local network.

This integration currently supports the **OUPES Mega 2** only.

## Features

- Battery percentage sensor
- Battery temperature sensor
- AC input power sensor
- Solar input power sensor
- Total input power sensor
- AC output power sensor
- Time remaining sensor
- Charge mode sensor
- AC output status
- DC output status

## Installation

1. Copy `custom_components/oupes_mega2` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from the Home Assistant UI.
4. Enter the device IP address, TCP port, device ID, and device key.

The TCP port is usually:

```text
5555
```

## Important

Close the OUPES mobile app while Home Assistant is polling the device.

The app and Home Assistant may conflict if both are connected to the power station at the same time.

## Finding the Device ID and Device Key

The integration needs the OUPES `device_id` and `device_key`.

These are not printed on the power station and usually are not shown by your router.

You get them from the OUPES/Cleanergy vendor API using the same email and password you use in the OUPES mobile app.

The API also returns the device MAC address. Use that MAC address to find the matching IP address in your router.

Do not share the API output publicly. It contains private device credentials.

### 1. Close the OUPES Mobile App

Close the app on your phone before running these commands.

You may need to log back into the app later.

### 2. Log In to the Vendor API

Replace `YOUR_EMAIL` and `YOUR_PASSWORD` with your OUPES app login.

```bash
curl -s 'https://api.upspowerstation.top/api/app/user/login' \
  -H 'Content-Type: application/json' \
  -H 'VersionName: 1.0.0' \
  -H 'lang: en' \
  -H 'package: com.cleanergy.app' \
  --data '{
    "mail": "YOUR_EMAIL",
    "passwd": "YOUR_PASSWORD",
    "lang": "en",
    "platform": "android",
    "systemVersion": 34
  }'
```

The response contains login tokens.

Copy one token for the next command. If the next command says to log in again, use the other token from the login response.

### 3. List Your Devices

Replace `YOUR_TOKEN` with the token from the login response.

```bash
curl -s "https://api.upspowerstation.top/api/app/device/list?token=YOUR_TOKEN&platform=android&lang=en&systemVersion=34" \
  -H 'VersionName: 1.0.0' \
  -H 'lang: en' \
  -H 'package: com.cleanergy.app' \
  | jq '.info.bind[] | {
      name,
      device_id,
      device_key,
      device_product_id,
      mac_address
    }'
```

Use the output values in Home Assistant:

| API value | Home Assistant field |
|---|---|
| `device_id` | Device ID |
| `device_key` | Device key |
| `mac_address` | Use this to find the device IP address in your router |

## Finding the IP Address

Open your router's DHCP/client list.

Find the device with the same MAC address returned by the API.

Use that IP address when adding the integration in Home Assistant.

If possible, reserve the IP address in your router so it does not change.

## Adding More Devices

To add another OUPES Mega 2, choose **Add entry** from the OUPES Mega 2 integration page in Home Assistant.

Each device needs its own IP address, device ID, and device key.

## Notes

- This integration uses local TCP polling.
- Normal polling does not rely on the cloud service.
- The vendor API is only used to find the setup credentials.
- Do not commit Home Assistant `.storage` files.
- Do not publish your `device_key`.

## Repository

- Source: <https://github.com/ryanbytes/ha-oupes-mega2>
- Issues: <https://github.com/ryanbytes/ha-oupes-mega2/issues>
