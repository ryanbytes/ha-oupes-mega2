"""OUPES Mega 2 sensors."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    PERCENTAGE,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OupesMega2Coordinator

_LOGGER = logging.getLogger(__name__)

# Max plausible kWh for a home battery system (sanity check on restore)
# OUPES Mega 2 is ~2.5kWh battery, even with months of throughput 10,000 kWh is generous
_MAX_ENERGY_KWH = 10_000


@dataclass
class OupesSensorDescription(SensorEntityDescription):
    key: str = ""


SENSORS: tuple[OupesSensorDescription, ...] = (
    OupesSensorDescription(
        key="battery_pct",
        name="Battery",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OupesSensorDescription(
        key="solar_power_w",
        name="Solar Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:solar-power",
    ),
    OupesSensorDescription(
        key="ac_input_power_w",
        name="AC Input Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:transmission-tower",
    ),
    OupesSensorDescription(
        key="total_input_power_w",
        name="Total Input Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OupesSensorDescription(
        key="ac_output_power_w",
        name="AC Output Power",
        native_unit_of_measurement=UnitOfPower.WATT,
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:power-socket",
    ),
    OupesSensorDescription(
        key="temperature_c",
        name="Temperature",
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    OupesSensorDescription(
        key="time_remaining_min",
        name="Time Remaining",
        native_unit_of_measurement=UnitOfTime.MINUTES,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:timer-outline",
    ),
    OupesSensorDescription(
        key="charge_mode",
        name="Charge Mode",
        icon="mdi:battery-charging",
    ),
)

# Energy sensors — device_class=ENERGY, state_class=TOTAL_INCREASING, unit=kWh
# These accumulate internally in the coordinator and restore across restarts.
ENERGY_SENSORS: tuple[OupesSensorDescription, ...] = (
    OupesSensorDescription(
        key="energy_solar_kwh",
        name="Solar Energy",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:solar-power",
    ),
    OupesSensorDescription(
        key="energy_ac_in_kwh",
        name="Grid Energy In",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:transmission-tower",
    ),
    OupesSensorDescription(
        key="energy_ac_out_kwh",
        name="Energy Out",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:power-socket",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OupesMega2Coordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list = [OupesSensor(coordinator, d) for d in SENSORS]
    entities += [OupesEnergySensor(coordinator, d) for d in ENERGY_SENSORS]
    async_add_entities(entities)


def _device_info(coordinator: OupesMega2Coordinator) -> dict:
    return {
        "identifiers": {(DOMAIN, coordinator.device_id)},
        "name": "OUPES Mega 2",
        "manufacturer": "OUPES",
        "model": "Mega 2",
    }


class OupesSensor(CoordinatorEntity, SensorEntity):
    entity_description: OupesSensorDescription

    def __init__(self, coordinator: OupesMega2Coordinator, description: OupesSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"oupes_mega2_{coordinator.device_id}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)


class OupesEnergySensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Energy sensor that accumulates kWh and restores across HA restarts."""

    entity_description: OupesSensorDescription

    def __init__(self, coordinator: OupesMega2Coordinator, description: OupesSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"oupes_mega2_{coordinator.device_id}_{description.key}"
        self._attr_device_info = _device_info(coordinator)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restore persisted kWh totals into the coordinator
        last = await self.async_get_last_state()
        if last and last.state not in (None, "unknown", "unavailable"):
            try:
                val = float(last.state)
            except ValueError:
                val = 0.0
            # Sanity check: discard obviously corrupted values
            if val < 0 or val > _MAX_ENERGY_KWH:
                _LOGGER.warning(
                    "OUPES: discarding corrupted energy restore for %s: %s",
                    self.entity_description.key, val,
                )
                val = 0.0
            key = self.entity_description.key
            if key == "energy_solar_kwh":
                self.coordinator._energy_solar_kwh = val
            elif key == "energy_ac_in_kwh":
                self.coordinator._energy_ac_in_kwh = val
            elif key == "energy_ac_out_kwh":
                self.coordinator._energy_ac_out_kwh = val

    @property
    def native_value(self):
        return self.coordinator.data.get(self.entity_description.key)
