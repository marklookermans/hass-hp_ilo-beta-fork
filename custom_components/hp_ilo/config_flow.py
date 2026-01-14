"""Config flow for HP iLO devices."""
from __future__ import annotations

import logging
from urllib.parse import urlparse

import voluptuous as vol
import hpilo

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    CONF_PROTOCOL,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_UNIQUE_ID,
    CONF_DESCRIPTION,
    ATTR_CONFIGURATION_URL,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .sensor import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class HpIloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the HP iLO config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self.config: dict = {}

    # ---------------------------------------------------------------------
    # SSDP DISCOVERY
    # ---------------------------------------------------------------------
    async def async_step_ssdp(
        self, discovery_info: SsdpServiceInfo
    ) -> FlowResult:
        """Handle SSDP discovery."""

        if not discovery_info.ssdp_server or not discovery_info.ssdp_server.startswith(
            "HP-iLO"
        ):
            return self.async_abort(reason="not_hp_ilo")

        parsed_url = urlparse(discovery_info.ssdp_location)

        self.config = {
            CONF_HOST: parsed_url.hostname,
            CONF_PORT: parsed_url.port or DEFAULT_PORT,
            CONF_PROTOCOL: parsed_url.scheme or "http",
            CONF_NAME: discovery_info.upnp.get(
                ssdp.ATTR_UPNP_FRIENDLY_NAME, "HP iLO"
            ),
            CONF_DESCRIPTION: discovery_info.upnp.get(
                ssdp.ATTR_UPNP_MODEL_NAME, ""
            ),
            CONF_UNIQUE_ID: discovery_info.ssdp_udn,
        }

        self.context[ATTR_CONFIGURATION_URL] = (
            f"{parsed_url.scheme}://{parsed_url.netloc}"
        )

        await self.async_set_unique_id(self.config[CONF_UNIQUE_ID])
        self._abort_if_unique_id_configured(updates=self.config)

        return await self.async_step_confirm()

    # ---------------------------------------------------------------------
    # MANUAL USER SETUP
    # ---------------------------------------------------------------------
    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle manual setup."""

        if user_input is not None:
            self.config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: user_input[CONF_PORT],
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_NAME: user_input[CONF_HOST].upper(),
            }
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): int,
                    vol.Required(CONF_PROTOCOL, default="http"): vol.In(
                        ["http", "https"]
                    ),
                }
            ),
        )

    # ---------------------------------------------------------------------
    # CONFIRMATION
    # ---------------------------------------------------------------------
    async def async_step_confirm(self, user_input=None) -> FlowResult:
        """Confirm the discovered or manually entered device."""

        if user_input is not None:
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={
                CONF_HOST: self.config.get(CONF_HOST),
                CONF_NAME: self.config.get(CONF_NAME),
            },
        )

    # ---------------------------------------------------------------------
    # AUTHENTICATION
    # ---------------------------------------------------------------------
    async def async_step_auth(self, user_input=None) -> FlowResult:
        """Authenticate against the HP iLO device."""

        errors = {}

        if user_input is not None:
            use_https = self.config.get(CONF_PROTOCOL) == "https"
            port = int(self.config.get(CONF_PORT, DEFAULT_PORT))

            try:
                ilo = hpilo.Ilo(
                    hostname=self.config[CONF_HOST],
                    login=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    port=port,
                    ssl=use_https,
                    timeout=10,
                )

                # Validate connection (blocking → executor)
                await self.hass.async_add_executor_job(ilo.get_host_data)

                self.config[CONF_USERNAME] = user_input[CONF_USERNAME]
                self.config[CONF_PASSWORD] = user_input[CONF_PASSWORD]

                return self.async_create_entry(
                    title=self.config[CONF_NAME],
                    data=self.config,
                )

            except hpilo.IloLoginFailed:
                errors["base"] = "invalid_auth"
            except hpilo.IloCommunicationError as err:
                _LOGGER.error("HP iLO communication error: %s", err)
                errors["base"] = "cannot_connect"
            except hpilo.IloError as err:
                _LOGGER.error("HP iLO error: %s", err)
                errors["base"] = "unknown"

        return self.async_show_form(
            step_id="auth",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_USERNAME, default="Administrator"): str,
                    vol.Required(CONF_PASSWORD): str,
                }
            ),
            errors=errors,
        )

    # ---------------------------------------------------------------------
    # YAML IMPORT
    # ---------------------------------------------------------------------
    async def async_step_import(self, import_info) -> FlowResult:
        """Import configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_info[CONF_HOST]})
        return await self.async_step_user(import_info)
