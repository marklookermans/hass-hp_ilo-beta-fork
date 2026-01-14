"""The HP Integrated Lights-Out (iLO) component."""
from __future__ import annotations

import logging
from datetime import timedelta
import hpilo

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST, CONF_PORT, CONF_USERNAME, CONF_PASSWORD, Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hp_ilo"
# Platforms die we laden
PLATFORMS = [Platform.SENSOR, Platform.BUTTON, Platform.BINARY_SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HP iLO from a config entry."""
    
    # Maak de Coordinator aan voor centrale polling
    coordinator = IloDataUpdateCoordinator(hass, entry)
    
    # Haal de eerste keer data op voordat we verder gaan
    await coordinator.async_config_entry_first_refresh()

    # Sla de coordinator op zodat sensor.py en binary_sensor.py deze kunnen gebruiken
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
    }

    # --- Service Registratie ---
    async def handle_power_action(call: ServiceCall):
        ilo = hpilo.Ilo(
            hostname=entry.data[CONF_HOST],
            login=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            port=entry.data.get(CONF_PORT, 443),
        )
        action = call.service
        try:
            if action == "reboot_server":
                await hass.async_add_executor_job(ilo.warm_boot)
            elif action == "shutdown_graceful":
                await hass.async_add_executor_job(ilo.press_pwr_button)
            elif action == "shutdown_hard":
                await hass.async_add_executor_job(lambda: ilo.press_pwr_button(hold=True))
            elif action == "power_on":
                await hass.async_add_executor_job(ilo.set_host_power, True)
            _LOGGER.info("iLO action %s successful on %s", action, entry.data[CONF_HOST])
        except Exception as err:
            _LOGGER.error("Error executing %s: %s", action, err)

    for service in ["reboot_server", "shutdown_graceful", "shutdown_hard", "power_on"]:
        hass.services.async_register(DOMAIN, service, handle_power_action)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

class IloDataUpdateCoordinator(DataUpdateCoordinator):
    """Klasse om data-verzameling te beheren."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry):
        super().__init__(
            hass, _LOGGER, name=f"{DOMAIN}_{entry.data[CONF_HOST]}",
            update_interval=timedelta(seconds=30),
        )
        self.entry = entry

    async def _async_update_data(self):
        """Haal alle data op in één batch verzoek."""
        return await self.hass.async_add_executor_job(self._get_ilo_data)

    def _get_ilo_data(self):
        try:
            ilo = hpilo.Ilo(
                hostname=self.entry.data[CONF_HOST],
                login=self.entry.data[CONF_USERNAME],
                password=self.entry.data[CONF_PASSWORD],
                port=self.entry.data.get(CONF_PORT, 443),
            )
            
            health = ilo.get_embedded_health()
            power_usage_raw = ilo.get_host_data()
            
            # Wattage zoeken
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
                "health_summary": health.get("health_at_a_glance", {}).get("status", "OK"),
            }
        except Exception as err:
            raise UpdateFailed(f"Communication error: {err}")

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
