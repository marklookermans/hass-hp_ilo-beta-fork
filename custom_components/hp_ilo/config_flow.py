"""Config flow voor HP iLO via Redfish API."""
from __future__ import annotations

import logging
from urllib.parse import urlparse  # Toegevoegd voor SSDP support

import voluptuous as vol
from redfish import redfish_client, AuthMethod

from homeassistant import config_entries
from homeassistant.components import ssdp
from homeassistant.const import (
    CONF_HOST,
    CONF_PORT,
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_NAME,
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, DEFAULT_PORT

_LOGGER = logging.getLogger(__name__)


class RedfishIloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow voor HP iLO via Redfish."""

    VERSION = 1

    def __init__(self) -> None:
        self.config: dict = {}

    # ---------------------------------------------------------------------
    # SSDP DISCOVERY
    # ---------------------------------------------------------------------
    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Probeer Redfish te detecteren via SSDP."""
        if not discovery_info.ssdp_server or "redfish" not in discovery_info.ssdp_server.lower():
            return self.async_abort(reason="not_redfish_supported")

        parsed_url = urlparse(discovery_info.ssdp_location)
        host = parsed_url.hostname
        port = parsed_url.port or DEFAULT_PORT

        self.config = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_NAME: f"iLO Redfish @ {host}",
        }

        self.context["configuration_url"] = f"https://{host}:{port}"
        await self.async_set_unique_id(f"redfish_ilo_{host}")
        self._abort_if_unique_id_configured(updates=self.config)

        return await self.async_step_user()

    # ---------------------------------------------------------------------
    # MANUELE INVOER
    # ---------------------------------------------------------------------
    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handmatige invoer van host, poort, credentials."""
        errors = {}

        if user_input is not None:
            self.config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
                CONF_NAME: user_input.get(CONF_NAME) or f"iLO Redfish @ {user_input[CONF_HOST]}",
            }
            return await self.async_step_auth()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=self.config.get(CONF_HOST, "")): str,
                    vol.Required(CONF_PORT, default=self.config.get(CONF_PORT, DEFAULT_PORT)): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required(CONF_USERNAME, default="Administrator"): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Optional(CONF_NAME, default=self.config.get(CONF_NAME, "")): str,
                }
            ),
            errors=errors,
        )

    # ---------------------------------------------------------------------
    # AUTHENTICATIE & TEST CONNECTIE
    # ---------------------------------------------------------------------
    async def async_step_auth(self, user_input=None) -> FlowResult:
        """Probeer in te loggen en een test call uit te voeren naar de API Root."""
        errors = {}

        try:
            base_url = f"https://{self.config[CONF_HOST]}:{self.config[CONF_PORT]}"

            def _test_connection():
                redfish_obj = redfish_client(
                    base_url=base_url,
                    username=self.config[CONF_USERNAME],
                    password=self.config[CONF_PASSWORD],
                    default_prefix="/redfish/v1/",
                    timeout=10
                )
                redfish_obj.login(auth=AuthMethod.SESSION)
                
                # TEST: We vragen de Root aan (/) in plaats van /Systems/1/
                # Dit voorkomt de 404 als de systeem-ID anders is dan "1"
                response = redfish_obj.get("/redfish/v1/")
                
                # Uitloggen om sessie-vervuiling op de iLO te voorkomen
                redfish_obj.logout()
                return response

            response = await self.hass.async_add_executor_job(_test_connection)

            if response.status != 200:
                raise Exception(f"Redfish request mislukt: status {response.status}")

            # Unique ID instellen
            unique_id = f"redfish_ilo_{self.config[CONF_HOST]}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured(updates=self.config)

            return self.async_create_entry(
                title=self.config[CONF_NAME],
                data=self.config,
            )

        except Exception as err:
            err_str = str(err).lower()
            _LOGGER.error("Redfish fout tijdens setup: %s", err)

            if "timeout" in err_str or "connection" in err_str:
                errors["base"] = "cannot_connect"
            elif "401" in err_str or "unauthorized" in err_str:
                errors["base"] = "invalid_auth"
            else:
                errors["base"] = "unknown"

        # Bij een fout gaan we terug naar het gebruikersscherm om gegevens te corrigeren
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_HOST, default=self.config[CONF_HOST]): str,
                vol.Required(CONF_PORT, default=self.config[CONF_PORT]): int,
                vol.Required(CONF_USERNAME, default=self.config[CONF_USERNAME]): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )
