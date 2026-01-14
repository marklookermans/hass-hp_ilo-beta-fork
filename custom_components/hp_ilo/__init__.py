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
from homeassistant.exceptions import ConfigEntryNotReady

_LOGGER = logging.getLogger(__name__)

DOMAIN = "hp_ilo"

# Hier voegen we de platforms toe die we ondersteunen
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entities of all platforms from a config entry."""
    
    # We slaan de entry data op zodat andere platforms erbij kunnen
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    # Test de verbinding kort om te zien of iLO bereikbaar is
    try:
        ilo_test = await hass.async_add_executor_job(
            lambda: hpilo.Ilo(
                hostname=entry.data[CONF_HOST],
                login=entry.data[CONF_USERNAME],
                password=entry.data[CONF_PASSWORD],
                port=entry.data.get(CONF_PORT, 443),
            )
        )
    except Exception as err:
        raise ConfigEntryNotReady(f"Kan geen verbinding maken met iLO: {err}")

    # --- Service Registratie ---
    
    async def handle_power_action(call: ServiceCall):
        """Voer een power actie uit."""
        # Haal de client op voor elke call (om sessie-timeouts te voorkomen)
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
                _LOGGER.info("iLO: Warm boot uitgevoerd op %s", entry.data[CONF_HOST])
            
            elif action == "shutdown_graceful":
                await hass.async_add_executor_job(ilo.press_pwr_button)
                _LOGGER.info("iLO: Graceful shutdown verzonden naar %s", entry.data[CONF_HOST])
            
            elif action == "shutdown_hard":
                await hass.async_add_executor_job(ilo.set_host_power, False)
                _LOGGER.warning("iLO: Harde shutdown uitgevoerd op %s", entry.data[CONF_HOST])
            
            elif action == "power_on":
                await hass.async_add_executor_job(ilo.set_host_power, True)
                _LOGGER.info("iLO: Server ingeschakeld op %s", entry.data[CONF_HOST])

        except Exception as err:
            _LOGGER.error("Fout tijdens uitvoeren van %s op iLO %s: %s", action, entry.data[CONF_HOST], err)

    # Registreer de services onder het domein 'hp_ilo'
    hass.services.async_register(DOMAIN, "reboot_server", handle_power_action)
    hass.services.async_register(DOMAIN, "shutdown_graceful", handle_power_action)
    hass.services.async_register(DOMAIN, "shutdown_hard", handle_power_action)
    hass.services.async_register(DOMAIN, "power_on", handle_power_action)

    # Laad de platforms (sensor.py en button.py)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry en ruim services op."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        
        # Als dit de laatste iLO was, verwijder dan de services volledig
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, "reboot_server")
            hass.services.async_remove(DOMAIN, "shutdown_graceful")
            hass.services.async_remove(DOMAIN, "shutdown_hard")
            hass.services.async_remove(DOMAIN, "power_on")

    return unload_ok
