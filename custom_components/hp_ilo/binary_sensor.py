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
from .sensor import IloDataUpdateCoordinator

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iLO binary sensors."""
    
    # We gebruiken dezelfde coordinator als de sensoren
    # Zo belasten we de iLO niet extra
    coordinator = hass.data[DOMAIN][entry.entry_id + "_coordinator"]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get("name", "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
    )

    async_add_entities([
        HpIloHealthBinarySensor(coordinator, device_info),
    ])

class HpIloHealthBinarySensor(BinarySensorEntity):
    """Representatie van de globale iLO Health status."""

    def __init__(self, coordinator, device_info):
        self.coordinator = coordinator
        self._attr_name = f"{device_info['name']} Global Health"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_global_health"
        self._attr_device_info = device_info
        self._attr_device_class = BinarySensorDeviceClass.PROBLEM

    @property
    def is_on(self) -> bool:
        """Return true als er een probleem is (status niet OK of Healthy)."""
        data = self.coordinator.data
        if not data or "health_summary" not in data:
            return False
            
        status = data["health_summary"].upper()
        # De sensor is 'ON' (Problem) als de status NIET OK of HEALTHY is
        return status not in ["OK", "HEALTHY"]

    @property
    def extra_state_attributes(self):
        """Voeg de ruwe status toe als attribuut."""
        return {
            "status": self.coordinator.data.get("health_summary", "Unknown")
        }
