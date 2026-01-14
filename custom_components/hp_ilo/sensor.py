"""Support for HP iLO sensors via Redfish/HPILO."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

import hpilo
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
    CONF_PORT,
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

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)

# AANGEPAST: Interval nu op 30 seconden
SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HP iLO sensors vanuit een config entry."""
    
    coordinator = IloDataUpdateCoordinator(hass, entry)
    
    # Eerste refresh bij opstarten
    await coordinator.async_config_entry_first_refresh()

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get(CONF_NAME, "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
        configuration_url=f"https://{entry.data[CONF_HOST]}",
    )

    sensors: list[SensorEntity] = []
    data = coordinator.data

    # 1. Temperatuur
    if "temperature" in data:
        for label, sensor_info in data["temperature"].items():
            if sensor_info.get("status") != "Not Installed":
                sensors.append(HpIloTemperatureSensor(coordinator, label, device_info))

    # 2. Fans
    if "fans" in data:
        for label, fan_info in data["fans"].items():
            sensors.append(HpIloFanSensor(coordinator, label, device_info))

    # 3. Power Status
    if "power_status" in data:
        sensors.append(HpIloPowerSensor(coordinator, device_info))

    # 4. Power On Time
    if "power_on_time" in data:
        sensors.append(HpIloPowerOnTimeSensor(coordinator, device_info))

    async_add_entities(sensors)


class IloDataUpdateCoordinator(DataUpdateCoordinator):
    """Centrale klasse om iLO data elke 30 seconden te verzamelen."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Haal alle data op in één call."""
        return await self.hass.async_add_executor_job(self._get_ilo_data)

    def _get_ilo_data(self) -> dict[str, Any]:
        """Sync verbinding met de iLO library."""
        try:
            ilo = hpilo.Ilo(
                hostname=self.entry.data[CONF_HOST],
                login=self.entry.data[CONF_USERNAME],
                password=self.entry.data[CONF_PASSWORD],
                port=self.entry.data.get(CONF_PORT, DEFAULT_PORT),
            )
            
            health = ilo.get_embedded_health()
            
            return {
                "temperature": health.get("temperature", {}),
                "fans": health.get("fans", {}),
                "power_status": ilo.get_host_power_status(),
                "power_on_time": ilo.get_server_power_on_time(),
            }
        except Exception as err:
            raise UpdateFailed(f"iLO onbereikbaar: {err}") from err


class HpIloBaseSensor(CoordinatorEntity, SensorEntity):
    """Basis voor iLO sensoren."""
    def __init__(self, coordinator: IloDataUpdateCoordinator, device_info: DeviceInfo):
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
    def native_value(self) -> float | None:
        temp_data = self.coordinator.data["temperature"].get(self._label)
        if temp_data:
            val = temp_data.get("currentreading")
            return val[0] if isinstance(val, (list, tuple)) else val
        return None


class HpIloFanSensor(HpIloBaseSensor):
    """Fan snelheid."""
    def __init__(self, coordinator, label, device_info):
        super().__init__(coordinator, device_info)
        self._label = label
        self._attr_name = f"{device_info['name']} Fan {label}"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_fan_{label.replace(' ', '_')}"
        self._attr_native_unit_of_measurement = PERCENTAGE
        self._attr_icon = "mdi:fan"
        self._attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def native_value(self) -> int | None:
        fan_data = self.coordinator.data["fans"].get(self._label)
        if fan_data:
            val = fan_data.get("speed")
            return val[0] if isinstance(val, (list, tuple)) else val
        return None


class HpIloPowerSensor(HpIloBaseSensor):
    """Power Status."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power Status"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_status"
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["ON", "OFF"]

    @property
    def native_value(self) -> str:
        status = self.coordinator.data.get("power_status", "UNKNOWN")
        return status.upper() if status else "UNKNOWN"


class HpIloPowerOnTimeSensor(HpIloBaseSensor):
    """Power On Time."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power On Time"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_on_time"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("power_on_time")
