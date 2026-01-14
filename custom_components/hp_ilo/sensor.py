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

# Polling interval op 30 seconden voor goede balans tussen realtime en belasting
SCAN_INTERVAL = timedelta(seconds=30)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the HP iLO sensors from a config entry."""
    
    coordinator = IloDataUpdateCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get(CONF_NAME, "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
        configuration_url=f"https://{entry.data[CONF_HOST]}",
    )

    sensors: list[SensorEntity] = []
    data = coordinator.data

    # 1. Temperatuur sensoren
    if "temperature" in data:
        for label, sensor_info in data["temperature"].items():
            if sensor_info.get("status") != "Not Installed":
                sensors.append(HpIloTemperatureSensor(coordinator, label, device_info))

    # 2. Fan sensoren
    if "fans" in data:
        for label, fan_info in data["fans"].items():
            sensors.append(HpIloFanSensor(coordinator, label, device_info))

    # 3. Status sensoren (Power Status & Uptime)
    sensors.append(HpIloPowerStatusSensor(coordinator, device_info))
    sensors.append(HpIloPowerOnTimeSensor(coordinator, device_info))

    # 4. NIEUW: Power Usage sensor (Wattage)
    if data.get("power_usage") is not None:
        sensors.append(HpIloPowerUsageSensor(coordinator, device_info))

    async_add_entities(sensors)


class IloDataUpdateCoordinator(DataUpdateCoordinator):
    """Central coordinator to poll iLO data every 30 seconds."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=SCAN_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from iLO via executor thread."""
        return await self.hass.async_add_executor_job(self._get_ilo_data)

    def _get_ilo_data(self) -> dict[str, Any]:
        """Sync call to get all health and power data."""
        try:
            ilo = hpilo.Ilo(
                hostname=self.entry.data[CONF_HOST],
                login=self.entry.data[CONF_USERNAME],
                password=self.entry.data[CONF_PASSWORD],
                port=self.entry.data.get(CONF_PORT, DEFAULT_PORT),
            )
            
            health = ilo.get_embedded_health()
            power_usage_raw = ilo.get_host_data()
            
            # Zoek naar wattage in de host data list
            power_watt = 0
            for item in power_usage_raw:
                if 'host_pwr_usage' in item:
                    power_watt = item['host_pwr_usage']
                    break

            return {
                "temperature": health.get("temperature", {}),
                "fans": health.get("fans", {}),
                "power_status": ilo.get_host_power_status(),
                "power_on_time": ilo.get_server_power_on_time(),
                "power_usage": power_watt,
            }
        except Exception as err:
            raise UpdateFailed(f"Error communicating with iLO: {err}") from err


class HpIloBaseSensor(CoordinatorEntity, SensorEntity):
    """Base class for iLO sensors."""
    def __init__(self, coordinator: IloDataUpdateCoordinator, device_info: DeviceInfo):
        super().__init__(coordinator)
        self._attr_device_info = device_info


class HpIloTemperatureSensor(HpIloBaseSensor):
    """Temperature sensor."""
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
    """Fan speed sensor."""
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


class HpIloPowerStatusSensor(HpIloBaseSensor):
    """Power Status sensor (ON/OFF)."""
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


class HpIloPowerUsageSensor(HpIloBaseSensor):
    """Real-time Power Usage sensor in Watts."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power Usage"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_usage"
        self._attr_native_unit_of_measurement = "W"
        self._attr_device_class = SensorDeviceClass.POWER
        self._attr_state_class = SensorStateClass.MEASUREMENT
        self._attr_icon = "mdi:lightning-bolt"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("power_usage")


class HpIloPowerOnTimeSensor(HpIloBaseSensor):
    """Server Power On Time sensor."""
    def __init__(self, coordinator, device_info):
        super().__init__(coordinator, device_info)
        self._attr_name = f"{device_info['name']} Power On Time"
        self._attr_unique_id = f"{coordinator.entry.entry_id}_power_on_time"
        self._attr_native_unit_of_measurement = UnitOfTime.MINUTES
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> int | None:
        return self.coordinator.data.get("power_on_time")
