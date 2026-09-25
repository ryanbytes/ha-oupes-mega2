"""OUPES Mega 2 binary sensors."""
from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OupesMega2Coordinator


@dataclass
class OupesBinarySensorDescription(BinarySensorEntityDescription):
    key: str = ""


BINARY_SENSORS: tuple[OupesBinarySensorDescription, ...] = (
    OupesBinarySensorDescription(
        key="ac_charging",
        name="AC Charging",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
    ),
    OupesBinarySensorDescription(
        key="ac_output_on",
        name="AC Output",
        icon="mdi:power-socket",
    ),
    OupesBinarySensorDescription(
        key="dc_output_on",
        name="DC Output",
        icon="mdi:car-battery",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: OupesMega2Coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        OupesBinarySensor(coordinator, description) for description in BINARY_SENSORS
    )


class OupesBinarySensor(CoordinatorEntity, BinarySensorEntity):
    entity_description: OupesBinarySensorDescription

    def __init__(
        self,
        coordinator: OupesMega2Coordinator,
        description: OupesBinarySensorDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"oupes_mega2_{coordinator.device_id}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, coordinator.device_id)},
            "name": "OUPES Mega 2",
            "manufacturer": "OUPES",
            "model": "Mega 2",
        }

    @property
    def is_on(self) -> bool | None:
        return self.coordinator.data.get(self.entity_description.key)
