"""Support for HP iLO sensors via Redfish/HPILO."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_USERNAME,
    PERCENTAGE,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=300)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HP iLO sensors vanuit een config entry."""
    
    # We gebruiken een Coordinator om te voorkomen dat elke sensor apart de iLO pollt
    coordinator = IloDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data[CONF_NAME],
        manufacturer="Hewlett Packard Enterprise",
        configuration_url=f"https://{entry.data[CONF_HOST]}",
    )

    sensors = []
    
    # Haal de data eenmalig op om te zien welke sensoren we kunnen aanmaken
    data = coordinator.data
    
    # 1. Temperatuur Sensoren
    if "temperature" in data:
        for sensor_id, sensor_data in data["temperature"].items():
            if sensor_data.get("status") != "Not Installed":
                sensors.append(
                    HpIloTemperatureSensor(coordinator, sensor_id, device_info, entry)
                )

    # 2. Fan Sensoren
    if "fans" in data:
        for fan_id, fan_data in data["fans"].items():
            sensors.append(
                HpIloFanSensor(coordinator, fan_id, device_info, entry)
            )

    # 3. Power Status
    if "power_status" in data:
        sensors.append(HpIloPowerSensor(coordinator, device_info, entry))

    async_add_entities(sensors)


class IloDataUpdateCoordinator(DataUpdateCoordinator):
    """Klasse om data centraal op te halen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Haal data op van de iLO (Redfish of hpilo library)."""
        try:
            # Hier voer je de logica uit om je data te vullen.
            # Voorbeeld structuur die de sensoren hieronder verwachten:
            return await self.hass.async_add_executor_job(self._get_ilo_data)
        except Exception as err:
            raise UpdateFailed(f"Fout bij communicatie met iLO: {err}")

    def _get_ilo_data(self):
        """Sync call naar iLO (uitgevoerd in executor)."""
        import hpilo
        ilo = hpilo.Ilo(
            hostname=self.entry.data[CONF_HOST],
            login=self.entry.data[CONF_USERNAME],
            password=self.entry.data[CONF_PASSWORD],
        )
        
        # Verzamel alle data in één dictionary
        health = ilo.get_embedded_health()
        return {
            "temperature": health.get("temperature", {}),
            "fans": health.get("fans", {}),
            "power_status": ilo.get_host_power_status(),
        }

class HpIloBaseSensor(CoordinatorEntity, SensorEntity):
    """Basis klasse voor iLO sensoren."""

    def __init__(self, coordinator, device_info, entry):
        super().__init__(coordinator)
        self._attr_device_info = device_info
        self.entry = entry

class HpIloTemperatureSensor(HpIloBaseSensor):
    """Temperatuur sensor."""

    def __init__(self, coordinator, sensor_id, device_info, entry):
        super().__init__(coordinator, device_info, entry)
        self.sensor_id = sensor_id
        self._attr_name = f"{entry.data[CONF_NAME]} Temp {sensor_id}"
        self._attr_unique_id = f"{entry.entry_id}_temp_{sensor_id}"
        self._attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
        self._attr_device_class = SensorDeviceClass.TEMPERATURE
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self):
        """Haal de waarde uit de gecachte coordinator data."""
        data = self.coordinator.data["temperature"].get(self.sensor_id)
        if data:
            # hpilo geeft vaak een lijst/tuple voor currentreading
            val = data.get("currentreading")
            return val[0] if isinstance(val, (list, tuple)) else val
        return None

class HpIloFanSensor(HpIloBaseSensor):
    """Fan snelheid sensor."""

    def __init__(self, coordinator, fan_id, device_info, entry):
        super().__init__(coordinator, device_info, entry)
        self.fan_id = fan_id
        self._attr_name = f"{entry.data[CONF_NAME]} Fan {fan_id}"
        self._attr_unique_id = f"{entry.entry_id}_fan_{fan_id}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:fan"

    @property
    def native_value(self):
        data = self.coordinator.data["fans"].get(self.fan_id)
        if data:
            val = data.get("speed")
            return val[0] if isinstance(val, (list, tuple)) else val
        return None

class HpIloPowerSensor(HpIloBaseSensor):
    """Power status sensor (ON/OFF)."""

    def __init__(self, coordinator, device_info, entry):
        super().__init__(coordinator, device_info, entry)
        self._attr_name = f"{entry.data[CONF_NAME]} Power Status"
        self._attr_unique_id = f"{entry.entry_id}_power"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["ON", "OFF"]

    @property
    def native_value(self):
        return self.coordinator.data.get("power_status")
