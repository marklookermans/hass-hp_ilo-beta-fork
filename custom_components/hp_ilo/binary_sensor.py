"""Support for HP iLO binary sensors."""
from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
# GEFIXT: We importeren de coordinator nu niet meer uit sensor.py
# omdat hij in __init__.py staat.

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iLO binary sensors."""
    
    # Haal de coordinator op uit de centrale opslag (gezet in __init__.py)
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get("name", "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
    )

    async_add_entities([
        HpIloHealthBinarySensor(coordinator, device_info),
    ])

class HpIloHealthBinarySensor(BinarySensorEntity):
    """Representation of the global iLO Health status."""

    def __init__(self, coordinator, device_info):
        self.coordinator = coordinator
        self._attr_name = f"{device_info['name']} Global Health"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_global_health"
        self._attr_device_info = device_info
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true if there is a problem (status is not OK)."""
        data = self.coordinator.data
        if not data:
            return False
            
        status = data.get("health_summary", "OK").upper()
        return status not in ["OK", "HEALTHY"]

    @property
    def extra_state_attributes(self):
        """Add raw status as attribute."""
        return {
            "status": self.coordinator.data.get("health_summary", "Unknown")
        }
