"""Support for HP iLO power buttons."""
from __future__ import annotations

import hpilo
from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, DEFAULT_PORT

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the iLO buttons."""
    device_info = DeviceInfo(
        identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
        name=entry.data.get("name", "HP iLO"),
        manufacturer="Hewlett Packard Enterprise",
    )

    async_add_entities([
        IloPowerButton(entry, device_info, "Power On", "power_on", "mdi:power-on"),
        IloPowerButton(entry, device_info, "Reboot (Warm)", "warm_boot", "mdi:restart"),
        IloPowerButton(entry, device_info, "Shutdown (Graceful)", "press_pwr_button", "mdi:power"),
        IloPowerButton(entry, device_info, "Shutdown (Hard - Press & Hold)", "hard_shutdown", "mdi:power-off"),
    ])

class IloPowerButton(ButtonEntity):
    """Representatie van een iLO power actie knop."""

    def __init__(self, entry, device_info, name, action_type, icon):
        self._entry = entry
        self._action_type = action_type
        self._attr_name = f"{device_info['name']} {name}"
        self._attr_unique_id = f"{entry.entry_id}_{action_type}"
        self._attr_device_info = device_info
        self._attr_icon = icon

    def _get_ilo_client(self):
        """Maak een nieuwe iLO client aan."""
        return hpilo.Ilo(
            hostname=self._entry.data[CONF_HOST],
            login=self._entry.data[CONF_USERNAME],
            password=self._entry.data[CONF_PASSWORD],
            port=self._entry.data.get(CONF_PORT, DEFAULT_PORT),
        )

    async def async_press(self) -> None:
        """Voer de actie uit wanneer op de knop wordt gedrukt."""
        ilo = await self.hass.async_add_executor_job(self._get_ilo_client)
        
        try:
            if self._action_type == "power_on":
                await self.hass.async_add_executor_job(ilo.set_host_power, True)
            elif self._action_type == "warm_boot":
                await self.hass.async_add_executor_job(ilo.warm_boot)
            elif self._action_type == "press_pwr_button":
                await self.hass.async_add_executor_job(ilo.press_pwr_button)
            elif self._action_type == "hard_shutdown":
                # GEFIXT: Gebruik hold=True om de fysieke knop 4 sec in te drukken
                await self.hass.async_add_executor_job(lambda: ilo.press_pwr_button(hold=True))
        except Exception as err:
            from homeassistant.exceptions import HomeAssistantError
            raise HomeAssistantError(f"iLO Actie mislukt: {err}")
