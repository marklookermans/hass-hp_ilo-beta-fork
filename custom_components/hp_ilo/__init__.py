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
PLATFORMS = [Platform.SENSOR, Platform.BUTTON]

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up entities of all platforms from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry

    async def handle_power_action(call: ServiceCall):
        """Handle power actions via services."""
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
                # GEFIXT: press_pwr_button
                await hass.async_add_executor_job(ilo.press_pwr_button)
            elif action == "shutdown_hard":
                # GEFIXT: press_pwr_button(hold=True)
                await hass.async_add_executor_job(lambda: ilo.press_pwr_button(hold=True))
            elif action == "power_on":
                await hass.async_add_executor_job(ilo.set_host_power, True)
            
            _LOGGER.info("iLO action %s executed on %s", action, entry.data[CONF_HOST])
        except Exception as err:
            _LOGGER.error("Error executing %s on %s: %s", action, entry.data[CONF_HOST], err)

    # Register services
    for service in ["reboot_server", "shutdown_graceful", "shutdown_hard", "power_on"]:
        hass.services.async_register(DOMAIN, service, handle_power_action)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok
