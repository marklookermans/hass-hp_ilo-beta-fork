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
                    timeout=120,  # Hoog genoeg om timeouts te voorkomen
                    ssl_verify=False,  # Self-signed certs
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
            except Exception as err:
                _LOGGER.exception("Unexpected error during iLO auth")
                errors["base"] = "unknown"
            finally:
                # Forceer sluiten van verbinding om idle-timeouts te voorkomen
                if 'ilo' in locals():  # Zorg dat ilo bestaat
                    try:
                        await self.hass.async_add_executor_job(ilo._close)
                    except Exception:
                        pass  # Ignore close errors

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
