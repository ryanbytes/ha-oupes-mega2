"""OUPES Mega 2 integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from .const import DOMAIN, CONF_DEVICE_ID, CONF_DEVICE_KEY
from .coordinator import OupesMega2Coordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

_SENSOR_KEYS = (
    "battery_pct",
    "solar_power_w",
    "ac_input_power_w",
    "total_input_power_w",
    "ac_output_power_w",
    "temperature_c",
    "time_remaining_min",
    "charge_mode",
    "energy_solar_kwh",
    "energy_ac_in_kwh",
    "energy_ac_out_kwh",
)
_BINARY_SENSOR_KEYS = (
    "ac_charging",
    "ac_output_on",
    "dc_output_on",
)


async def _async_migrate_entity_unique_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> None:
    """Migrate legacy single-device unique IDs to device-scoped IDs.

    This preserves existing entity_ids for current users while allowing
    additional OUPES devices to be added without unique_id collisions.
    """
    ent_reg = er.async_get(hass)
    device_id = entry.data[CONF_DEVICE_ID]
    entries_by_unique_id = {
        entity_entry.unique_id: entity_entry
        for entity_entry in er.async_entries_for_config_entry(ent_reg, entry.entry_id)
    }
    legacy_to_new = [
        (f"oupes_mega2_{key}", f"oupes_mega2_{device_id}_{key}")
        for key in (*_SENSOR_KEYS, *_BINARY_SENSOR_KEYS)
    ]

    for legacy_unique_id, new_unique_id in legacy_to_new:
        legacy_entry = entries_by_unique_id.get(legacy_unique_id)
        if not legacy_entry:
            continue

        scoped_entry = entries_by_unique_id.get(new_unique_id)
        if scoped_entry and scoped_entry.entity_id != legacy_entry.entity_id:
            ent_reg.async_remove(scoped_entry.entity_id)
            _LOGGER.info(
                "Removed duplicate OUPES entity %s so %s can keep its entity_id",
                scoped_entry.entity_id,
                legacy_entry.entity_id,
            )

        try:
            ent_reg.async_update_entity(
                legacy_entry.entity_id,
                new_unique_id=new_unique_id,
            )
            _LOGGER.info(
                "Migrated OUPES entity unique_id for %s to %s",
                legacy_entry.entity_id,
                new_unique_id,
            )
        except ValueError as err:
            _LOGGER.warning(
                "Unable to migrate OUPES unique_id for %s: %s",
                legacy_entry.entity_id,
                err,
            )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    await _async_migrate_entity_unique_ids(hass, entry)
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
