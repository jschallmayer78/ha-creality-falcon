"""Config- und Options-Flow."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FalconApi, FalconError
from .const import (
    CANDIDATE_PORTS,
    CONF_CAMERA_PORT,
    CONF_SCAN_INTERVAL,
    DEFAULT_CAMERA_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)
from .coordinator import FalconConfigEntry

_LOGGER = logging.getLogger(__name__)


class FalconConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            host = user_input[CONF_HOST].strip()
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            port = await self._detect_port(host, user_input[CONF_PORT])
            if port is None:
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=user_input[CONF_NAME],
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_CAMERA_PORT: user_input[CONF_CAMERA_PORT],
                        CONF_NAME: user_input[CONF_NAME],
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST): str,
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.Coerce(int),
                vol.Required(CONF_CAMERA_PORT, default=DEFAULT_CAMERA_PORT): vol.Coerce(int),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(schema, user_input),
            errors=errors,
        )

    async def _detect_port(self, host: str, preferred: int) -> int | None:
        """Angegebenen Port testen, sonst die bekannten Kandidaten."""
        session = async_get_clientsession(self.hass)
        ports = [preferred, *[p for p in CANDIDATE_PORTS if p != preferred]]
        for port in ports:
            try:
                await FalconApi(session, host, port).get_progress()
            except FalconError as err:
                _LOGGER.debug("Falcon %s:%s antwortet nicht: %s", host, port, err)
                continue
            return port
        return None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: FalconConfigEntry) -> OptionsFlow:
        return FalconOptionsFlow()


class FalconOptionsFlow(OptionsFlow):
    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                        vol.Coerce(int), vol.Range(min=2, max=300)
                    )
                }
            ),
        )
