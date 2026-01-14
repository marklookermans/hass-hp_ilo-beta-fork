"""The HP Integrated Lights-Out (iLO) component."""
from __future__ import annotations

import logging
import hpilo
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant, ServiceCall

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hp_ilo"
PLATFORMS = [Platform.SENSOR]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entities of all platforms from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    # --- Service Sectie ---
    
    def get_ilo_client():
        """Helper om een iLO client te maken."""
        return hpilo.Ilo(
            hostname=entry.data[CONF_HOST],
            login=entry.data[CONF_USERNAME],
            password=entry.data[CONF_PASSWORD],
            port=entry.data.get(CONF_PORT, 443),
        )

    async def handle_power_action(call: ServiceCall):
        """Voer een power actie uit op de server."""
        action = call.service
        ilo = await hass.async_add_executor_job(get_ilo_client)

        try:
            if action == "reboot_server":
                _LOGGER.info("iLO: Warm boot uitgevoerd op %s", entry.data[CONF_HOST])
                await hass.async_add_executor_job(ilo.warm_boot)
            
            elif action == "shutdown_graceful":
                _LOGGER.info("iLO: Graceful shutdown (power button press) op %s", entry.data[CONF_HOST])
                await hass.async_add_executor_job(ilo.press_pwr_button)
            
            elif action == "shutdown_hard":
                _LOGGER.warning("iLO: HARD shutdown uitgevoerd op %s", entry.data[CONF_HOST])
                await hass.async_add_executor_job(ilo.set_host_power, False)
            
            elif action == "power_on":
                _LOGGER.info("iLO: Server inschakelen op %s", entry.data[CONF_HOST])
                await hass.async_add_executor_job(ilo.set_host_power, True)

        except Exception as err:
            _LOGGER.error("Fout tijdens iLO power actie %s: %s", action, err)

    # Registreer de services specifiek voor dit domein
    hass.services.async_register(DOMAIN, "reboot_server", handle_power_action)
    hass.services.async_register(DOMAIN, "shutdown_graceful", handle_power_action)
    hass.services.async_register(DOMAIN, "shutdown_hard", handle_power_action)
    hass.services.async_register(DOMAIN, "power_on", handle_power_action)

    # --- Einde Service Sectie ---

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Verwijder services als de laatste entry wordt verwijderd
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reboot_server")
            hass.services.async_remove(DOMAIN, "shutdown_graceful")
            hass.services.async_remove(DOMAIN, "shutdown_hard")
            hass.services.async_remove(DOMAIN, "power_on")
            
    return unload_ok
