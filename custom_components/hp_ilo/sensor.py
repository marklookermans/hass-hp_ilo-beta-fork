"""Support for HP iLO sensors."""
from __future__ import annotations

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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Set up iLO sensors."""
    # Haal de coordinator op die in __init__.py is aangemaakt
    coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get(CONF_NAME, "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
    )

    sensors = []
    data = coordinator.data

    # Voeg alle sensors toe op basis van de opgehaalde data
    if "temperature" in data:
        for label in data["temperature"]:
            sensors.append(HpIloTemperatureSensor(coordinator, label, device_info))

    if "fans" in data:
        for label in data["fans"]:
            sensors.append(HpIloFanSensor(coordinator, label, device_info))

    sensors.append(HpIloPowerStatusSensor(coordinator, device_info))
    sensors.append(HpIloPowerOnTimeSensor(coordinator, device_info))
    sensors.append(HpIloPowerUsageSensor(coordinator, device_info))

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
        self._attr_unique_id = f"{coordinator.entry.entry_id}_temp_{label}"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        temp = self.coordinator.data["temperature"].get(self._label)
        return temp.get("currentreading") if temp else None

class HpIloFanSensor(HpIloBaseSensor):
    """Fan snelheid sensor."""
    def __init__(self, coordinator, label, device_info):
        super().__init__(coordinator, device_info)
        self._label = label
        self._attr_name = f"{device_info['name']} Fan {label}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fan_{label}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:fan"

    @property
    def native_value(self):
        fan = self.coordinator.data["fans"].get(self._label)
        return fan.get("speed") if fan else None

class HpIloPowerUsageSensor(HpIloBaseSensor):
    """Real-time Wattage sensor."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power Usage"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_usage"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        return self.coordinator.data.get("power_usage")

class HpIloPowerStatusSensor(HpIloBaseSensor):
    """Power ON/OFF sensor."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power Status"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_status"

    @property
    def native_value(self):
        return self.coordinator.data.get("power_status")

class HpIloPowerOnTimeSensor(HpIloBaseSensor):
    """Uptime sensor."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power On Time"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_uptime"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES

    @property
    def native_value(self):
        return self.coordinator.data.get("power_on_time")
