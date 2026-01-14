"""Config flow voor HP iLO via Redfish."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import voluptuous as vol
from redfish import redfish_client, AuthMethod

from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
)
from homeassistant.data_entry_flow import FlowResult

from .const import DOMAIN, DEFAULT_PORT  # DEFAULT_PORT = 443

_LOGGER = logging.getLogger(__name__)

class RedfishIloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Redfish-based config flow for HP iLO."""

    VERSION = 1

    def __init__(self) -> None:
        self.config = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:
            self.config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_NAME: f"iLO Redfish @ {user_input[CONF_HOST]}",
            }
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                vol.Required(CONF_USERNAME, default="Administrator"): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )

    async def async_step_confirm(self, user_input=None) -> FlowResult:
        if user_input is not None:
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"host": self.config[CONF_HOST]},
        )

    async def async_step_auth(self, user_input=None) -> FlowResult:
        errors = {}
        if user_input is not None:  # Extra auth als nodig, maar meestal in user
            pass

        try:
            base_url = f"https://{self.config[CONF_HOST]}:{self.config[CONF_PORT]}"
            redfish_obj = await self.hass.async_add_executor_job(
                redfish_client,
                base_url=base_url,
                username=self.config[CONF_USERNAME],
                password=self.config[CONF_PASSWORD],
                default_prefix="/redfish/v1/",
            )
            await self.hass.async_add_executor_job(redfish_obj.login, auth=AuthMethod.SESSION)

            # Test call
            response = await self.hass.async_add_executor_job(
                redfish_obj.get, "/Systems/1/"
            )
            if response.status != 200:
                raise Exception("Redfish test failed")

            # Succes
            unique_id = f"redfish_ilo_{self.config[CONF_HOST]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            return self.async_create_entry(
                title=self.config[CONF_NAME],
                data=self.config,
            )

        except Exception as err:
            _LOGGER.error("Redfish connectie fout: %s", err)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema({}),  # Kan leeg als auth al in user zit
            errors=errors,
        )
