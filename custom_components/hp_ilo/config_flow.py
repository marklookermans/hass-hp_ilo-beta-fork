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
)
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.service_info.ssdp import SsdpServiceInfo

from .const import DOMAIN, DEFAULT_PORT  # Zorg dat je const.py hebt met DEFAULT_PORT = 443

_LOGGER = logging.getLogger(__name__)


class HpIloFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the HP iLO config flow."""

    VERSION = 1

    def __init__(self) -> None:
        self.config: dict = {}

    # ---------------------------------------------------------------------
    # SSDP DISCOVERY
    # ---------------------------------------------------------------------
    async def async_step_ssdp(self, discovery_info: SsdpServiceInfo) -> FlowResult:
        """Handle SSDP discovery."""
        if not discovery_info.ssdp_server or not discovery_info.ssdp_server.startswith("HP-iLO"):
            return self.async_abort(reason="not_hp_ilo")

        parsed_url = urlparse(discovery_info.ssdp_location)
        host = parsed_url.hostname
        port = parsed_url.port or DEFAULT_PORT
        protocol = parsed_url.scheme or "https"  # iLO defaults vaak naar https

        self.config = {
            CONF_HOST: host,
            CONF_PORT: port,
            CONF_PROTOCOL: protocol,
            CONF_NAME: f"HP iLO @ {host}",
            CONF_UNIQUE_ID: discovery_info.ssdp_udn or f"hp_ilo_{host}_{port}",
        }

        self.context["configuration_url"] = f"{protocol}://{host}:{port}"

        await self.async_set_unique_id(self.config[CONF_UNIQUE_ID])
        self._abort_if_unique_id_configured(updates=self.config)

        return await self.async_step_confirm()

    # ---------------------------------------------------------------------
    # MANUAL USER SETUP
    # ---------------------------------------------------------------------
    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle manual setup."""
        errors = {}

        if user_input is not None:
            self.config = {
                CONF_HOST: user_input[CONF_HOST],
                CONF_PORT: int(user_input[CONF_PORT]),
                CONF_PROTOCOL: user_input[CONF_PROTOCOL],
                CONF_NAME: f"HP iLO @ {user_input[CONF_HOST]}",
            }
            return await self.async_step_confirm()

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                        vol.Coerce(int), vol.Range(min=1, max=65535)
                    ),
                    vol.Required(CONF_PROTOCOL, default="https"): vol.In(["http", "https"]),
                }
            ),
            errors=errors,
        )

    # ---------------------------------------------------------------------
    # CONFIRMATION + NAME OVERRIDE
    # ---------------------------------------------------------------------
    async def async_step_confirm(self, user_input=None) -> FlowResult:
        """Confirm the discovered or manually entered device + allow name override."""
        if user_input is not None:
            self.config[CONF_NAME] = user_input[CONF_NAME].strip()
            return await self.async_step_auth()

        default_name = self.config.get(CONF_NAME, "HP iLO")

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=default_name): str,
                }
            ),
            description_placeholders={
                "host": self.config.get(CONF_HOST),
                "name": self.config.get(CONF_NAME),
            },
        )

    # ---------------------------------------------------------------------
    # AUTHENTICATION
    # ---------------------------------------------------------------------
    async def async_step_auth(self, user_input=None) -> FlowResult:
        """Authenticate against the HP iLO device."""
        errors = {}

        if user_input is not None:
            port = int(self.config.get(CONF_PORT, DEFAULT_PORT))
            protocol = self.config.get(CONF_PROTOCOL, "https")

            try:
                ilo = hpilo.Ilo(
                    hostname=self.config[CONF_HOST],
                    login=user_input[CONF_USERNAME],
                    password=user_input[CONF_PASSWORD],
                    port=port,
                    protocol=protocol,
                    timeout=20,
                    ssl_verify=False,           # Meest kritieke fix – self-signed certs
                )

                # Test verbinding (blocking → executor)
                host_data = await self.hass.async_add_executor_job(ilo.get_host_data)

                # Probeer serial voor betere unique_id
                serial = (
                    host_data.get("serial_number")
                    or host_data.get("SerialNumber")
                    or host_data.get("host", {}).get("serial_number")
                )

                unique_id = (
                    f"hp_ilo_{serial}" if serial else
                    f"hp_ilo_{self.config[CONF_HOST]}_{port}"
                )

                await self.async_set_unique_id(unique_id)
                self._abort_if_unique_id_configured(updates=self.config)

                self.config[CONF_USERNAME] = user_input[CONF_USERNAME]
                self.config[CONF_PASSWORD] = user_input[CONF_PASSWORD]

                return self.async_create_entry(
                    title=self.config[CONF_NAME],
                    data=self.config,
                )

            except hpilo.IloLoginFailed:
                errors["base"] = "invalid_auth"
            except hpilo.IloCommunicationError as err:
                _LOGGER.error("iLO communication error: %s", err)
                errors["base"] = "cannot_connect"
            except hpilo.IloError as err:
                _LOGGER.error("iLO error: %s", err)
                errors["base"] = "unknown"
            except Exception as err:  # Fallback
                _LOGGER.exception("Unexpected error during iLO auth")
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
    # YAML IMPORT (optioneel – als je nog legacy YAML ondersteunt)
    # ---------------------------------------------------------------------
    async def async_step_import(self, import_info) -> FlowResult:
        """Import configuration from configuration.yaml."""
        self._async_abort_entries_match({CONF_HOST: import_info[CONF_HOST]})
        self.config = import_info.copy()
        return await self.async_step_auth()  # Ga direct naar auth
