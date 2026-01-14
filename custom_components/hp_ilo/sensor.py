"""Support for HP iLO sensors."""
from __future__ import annotations

import logging
from homeassistant.components.sensor import (
    SensorDeviceClass, SensorEntity, SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_NAME, PERCENTAGE, UnitOfTemperature, UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up iLO sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get(CONF_NAME, "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
    )

    sensors = []
    data = coordinator.data

    if not data:
        _LOGGER.error("Geen data ontvangen van iLO coordinator")
        return

    # Dynamische sensoren (Temperatuur & Fans)
    # We controleren of de data aanwezig is en of het een dictionary is
    temp_data = data.get("temperature", {})
    if isinstance(temp_data, dict):
        for label in temp_data:
            sensors.append(HpIloTemperatureSensor(coordinator, label, device_info))

    fan_data = data.get("fans", {})
    if isinstance(fan_data, dict):
        for label in fan_data:
            sensors.append(HpIloFanSensor(coordinator, label, device_info))

    # Statische sensoren
    sensors.extend([
        HpIloPowerStatusSensor(coordinator, device_info),
        HpIloPowerOnTimeSensor(coordinator, device_info),
        HpIloPowerUsageSensor(coordinator, device_info),
    ])

    async_add_entities(sensors)

class HpIloBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class voor iLO sensors."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator)
        self._attr_device_info = device_info

class HpIloTemperatureSensor(HpIloBaseSensor):
    """Temperatuur sensor."""
    def __init__(self, coordinator, label, device_info):
        super().__init__(coordinator, device_info)
        self._label = label
        self._attr_name = f"{device_info['name']} Temp {label}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_temp_{label.replace(' ', '_')}"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        # Controleer op verschillende data formaten (dict of list)
        temp = self.coordinator.data.get("temperature", {}).get(self._label)
        if isinstance(temp, dict):
            val = temp.get("currentreading")
            # iLO geeft soms [waarde, eenheid], we willen alleen de waarde
            return val[0] if isinstance(val, list) else val
        return None

class HpIloFanSensor(HpIloBaseSensor):
    """Fan snelheid sensor."""
    def __init__(self, coordinator, label, device_info):
        super().__init__(coordinator, device_info)
        self._label = label
        self._attr_name = f"{device_info['name']} Fan {label}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fan_{label.replace(' ', '_')}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:fan"

    @property
    def native_value(self):
        fan = self.coordinator.data.get("fans", {}).get(self._label)
        if isinstance(fan, dict):
            val = fan.get("speed")
            return val[0] if isinstance(val, list) else val
        return None

# ... (De rest van de klassen PowerUsage, PowerStatus en PowerOnTime blijven gelijk aan je vorige sensor.py)
