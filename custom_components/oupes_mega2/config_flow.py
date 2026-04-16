"""Config flow for OUPES Mega 2."""
from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant

from .coordinator import _DeviceConnection
from .const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICE_KEY, DEFAULT_PORT

STEP_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST, default="192.168.1.100"): str,
        vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
        vol.Required(CONF_DEVICE_ID): str,
        vol.Required(CONF_DEVICE_KEY): str,
    }
)


def _validate_connection(host: str, port: int, device_id: str, device_key: str) -> None:
    conn = _DeviceConnection(host, port, device_id, device_key)
    try:
        data = conn.query()
        if not data:
            raise ValueError("Device returned no data — is the OUPES app closed?")
    finally:
        conn.close()


async def _validate(hass: HomeAssistant, data: dict) -> None:
    await hass.async_add_executor_job(
        _validate_connection,
        data[CONF_HOST],
        data[CONF_PORT],
        data[CONF_DEVICE_ID],
        data[CONF_DEVICE_KEY],
    )


class OupesMega2ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the OUPES Mega 2 config flow."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            try:
                await _validate(self.hass, user_input)
            except ValueError as e:
                errors["base"] = str(e)
            except Exception:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title="OUPES Mega 2", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_SCHEMA,
            errors=errors,
        )
