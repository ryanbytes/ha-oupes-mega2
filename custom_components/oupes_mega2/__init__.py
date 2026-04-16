"""OUPES Mega 2 integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICE_KEY
from .coordinator import OupesMega2Coordinator

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinator = OupesMega2Coordinator(
        hass,
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        device_id=entry.data[CONF_DEVICE_ID],
        device_key=entry.data[CONF_DEVICE_KEY],
    )
    await coordinator.async_config_entry_first_refresh()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
