"""OUPES Mega 2 DataUpdateCoordinator — direct TCP polling, no MQTT."""
from __future__ import annotations

import json
import socket
import time
import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

POLL_INTERVAL = timedelta(seconds=3)
THRESHOLD = 3        # watts — below this is noise
MAX_CONSECUTIVE_FAILURES = 4  # return stale data for up to this many failures

ATTR_GROUPS = [
    [1, 3, 4, 30, 32, 51, 105],
    [5, 21, 22, 23],
]


def _parse_lines(raw: bytes) -> dict[int, float | int]:
    """Parse newline-delimited JSON responses into a merged attr dict."""
    data: dict[int, float | int] = {}
    for line in raw.split(b"\n"):
        line = line.strip()
        if not line:
            continue
        try:
            parsed = json.loads(line)
            d = parsed.get("msg", {}).get("data", {})
            if d:
                data.update({int(k): v for k, v in d.items()})
        except Exception:
            pass
    return data


class _DeviceConnection:
    """Persistent TCP connection to the OUPES device."""

    def __init__(self, host: str, port: int, device_id: str, device_key: str) -> None:
        self._host = host
        self._port = port
        self._device_id = device_id
        self._device_key = device_key
        self._sock: socket.socket | None = None

    def close(self) -> None:
        if self._sock is not None:
            try:
                self._sock.close()
            except Exception:
                pass
            self._sock = None

    def _connect(self) -> None:
        """Open TCP socket and subscribe."""
        self.close()
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(8)
        s.connect((self._host, self._port))
        subscribe = (
            f"cmd=subscribe&topic=device_{self._device_id}"
            f"&from=control&device_id={self._device_id}"
            f"&device_key={self._device_key}\r\n"
        )
        s.sendall(subscribe.encode())
        # Wait for and consume the subscribe ACK (which may contain data)
        s.settimeout(3)
        try:
            s.recv(8192)
        except Exception:
            pass
        self._sock = s

    def query(self) -> dict[int, float | int]:
        """Send attr queries and return merged data. Reconnects if needed."""
        # Ensure we have a connection
        if self._sock is None:
            _LOGGER.debug("OUPES: no socket, connecting")
            self._connect()
            _LOGGER.debug("OUPES: connected OK")

        try:
            data = self._query_on_socket()
            _LOGGER.debug("OUPES: query OK, %d attrs", len(data))
            return data
        except Exception as err:
            # Connection went stale — reconnect once and retry
            _LOGGER.warning("OUPES socket stale (%s), reconnecting", err)
            try:
                self._connect()
                data = self._query_on_socket()
                _LOGGER.debug("OUPES: reconnect+query OK, %d attrs", len(data))
                return data
            except Exception:
                self.close()
                raise

    def _query_on_socket(self) -> dict[int, float | int]:
        """Send queries on the existing socket and read responses."""
        s = self._sock
        if s is None:
            raise ConnectionError("No socket")

        for attrs in ATTR_GROUPS:
            sn = str(int(time.time() * 1000))
            msg = json.dumps({"msg": {"attr": attrs}, "pv": 0, "cmd": 2, "sn": sn}) + "\r\n"
            s.sendall(msg.encode())
            time.sleep(0.05)

        # Read with generous timeout — WiFi latency can spike to 200ms+
        raw = b""
        s.settimeout(1.0)
        deadline = time.time() + 3.0
        while time.time() < deadline:
            try:
                chunk = s.recv(8192)
                if not chunk:
                    raise ConnectionError("Connection closed by device")
                raw += chunk
            except socket.timeout:
                # No more data within timeout — check if we have enough
                if raw:
                    break
            except Exception:
                raise

        data = _parse_lines(raw)
        if not data:
            raise ValueError("No attr data in response")
        return data


def _derive(raw: dict) -> dict:
    """Build the final sensor dict from raw attr data."""
    solar_w = round((raw.get(23) or 0), 1)
    total_in_w = round((raw.get(21) or 0), 1)
    ac_in_w = round((raw.get(22) or 0), 1)
    ac_out_w = round((raw.get(5) or 0), 1)
    battery_pct = raw.get(3)
    # The Cleanergy app maps attr 32 to tempFV, stored as tenths of a degree F.
    temp_f_raw = raw.get(32)
    temp_c = None if temp_f_raw is None else round(((temp_f_raw * 0.1) - 32) / 1.8, 1)
    time_remaining = raw.get(30)
    switch_value = int(raw.get(1) or 0)
    ac_output_on = bool(switch_value & 0b0001)
    dc_output_on = bool(switch_value & 0b0110)

    # Charge mode from actual power values (device attr 1 is unreliable)
    if solar_w > THRESHOLD and ac_in_w > THRESHOLD:
        charge_mode = "AC + Solar Charging"
    elif solar_w > THRESHOLD:
        charge_mode = "Solar Charging"
    elif ac_in_w > THRESHOLD:
        charge_mode = "AC Charging"
    elif battery_pct is not None and battery_pct >= 100:
        charge_mode = "Standby"
    else:
        charge_mode = "Discharging"

    ac_charging = ac_in_w > THRESHOLD

    return {
        "solar_power_w": solar_w,
        "ac_input_power_w": ac_in_w,
        "total_input_power_w": total_in_w,
        "ac_output_power_w": ac_out_w,
        "battery_pct": battery_pct,
        "temperature_c": temp_c,
        "time_remaining_min": time_remaining,
        "charge_mode": charge_mode,
        "ac_charging": ac_charging,
        "ac_output_on": ac_output_on,
        "dc_output_on": dc_output_on,
    }


class OupesMega2Coordinator(DataUpdateCoordinator):
    """Coordinator that polls the OUPES Mega 2 via TCP."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        device_id: str,
        device_key: str,
    ) -> None:
        self.host = host
        self.port = port
        self.device_id = device_id
        self.device_key = device_key

        self._conn = _DeviceConnection(host, port, device_id, device_key)
        self._consecutive_failures: int = 0
        self._last_good_data: dict | None = None

        # Cumulative energy accumulators (kWh), restored by energy sensor on startup
        self._energy_solar_kwh: float = 0.0
        self._energy_ac_in_kwh: float = 0.0
        self._energy_ac_out_kwh: float = 0.0
        self._last_update_time: float | None = None

        super().__init__(hass, _LOGGER, name="OUPES Mega 2", update_interval=POLL_INTERVAL)

    def restore_energy(self, solar: float, ac_in: float, ac_out: float) -> None:
        """Called by energy sensors at startup to restore persisted kWh totals."""
        self._energy_solar_kwh = solar
        self._energy_ac_in_kwh = ac_in
        self._energy_ac_out_kwh = ac_out

    def _accumulate_energy(self, data: dict) -> None:
        """Integrate W readings into kWh accumulators using elapsed time."""
        now = time.monotonic()
        if self._last_update_time is not None:
            elapsed_h = (now - self._last_update_time) / 3600.0
            # Cap at 2x poll interval to avoid huge jumps after outages
            elapsed_h = min(elapsed_h, POLL_INTERVAL.total_seconds() * 2 / 3600.0)
            self._energy_solar_kwh += data["solar_power_w"] * elapsed_h / 1000.0
            self._energy_ac_in_kwh += data["ac_input_power_w"] * elapsed_h / 1000.0
            self._energy_ac_out_kwh += data["ac_output_power_w"] * elapsed_h / 1000.0
        self._last_update_time = now

    def _do_query(self) -> dict[int, float | int]:
        """Blocking query using persistent connection."""
        return self._conn.query()

    async def _async_update_data(self) -> dict:
        _LOGGER.debug("OUPES: _async_update_data called")
        try:
            raw = await self.hass.async_add_executor_job(self._do_query)
        except Exception as err:
            self._consecutive_failures += 1
            _LOGGER.warning(
                "OUPES poll failed (%s/%s): %s",
                self._consecutive_failures, MAX_CONSECUTIVE_FAILURES, err,
            )
            if self._consecutive_failures <= MAX_CONSECUTIVE_FAILURES and self._last_good_data is not None:
                _LOGGER.debug("OUPES: returning stale data")
                return self._last_good_data
            raise UpdateFailed(
                f"Cannot reach OUPES device ({self._consecutive_failures} consecutive failures): {err}"
            ) from err

        self._consecutive_failures = 0
        data = _derive(raw)
        self._accumulate_energy(data)

        data["energy_solar_kwh"] = round(self._energy_solar_kwh, 4)
        data["energy_ac_in_kwh"] = round(self._energy_ac_in_kwh, 4)
        data["energy_ac_out_kwh"] = round(self._energy_ac_out_kwh, 4)

        self._last_good_data = data
        _LOGGER.debug("OUPES: update complete, battery=%s%%", data.get("battery_pct"))
        return data
