"""Config flow for Gatekeeper HA."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlowWithConfigEntry
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import *

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Optional("guest_port", default=DEFAULT_GUEST_PAGE_PORT): vol.All(
            vol.Coerce(int), vol.Range(min=1024, max=65535)
        ),
        vol.Optional("default_expiry_hours", default=DEFAULT_EXPIRY_HOURS): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=8760)
        ),
    }
)


class GatekeeperConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Gatekeeper HA."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=STEP_USER_DATA_SCHEMA,
                description_placeholders={
                    "port": str(DEFAULT_GUEST_PAGE_PORT),
                    "expiry": str(DEFAULT_EXPIRY_HOURS),
                },
            )

        return self.async_create_entry(
            title="Gatekeeper HA",
            data={},
            options={
                "guest_port": user_input["guest_port"],
                "default_expiry_hours": user_input["default_expiry_hours"],
            },
        )

    async def async_step_import(self, import_data: dict[str, Any]) -> ConfigFlowResult:
        """Import from YAML config."""
        return await self.async_step_user(import_data)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return GatekeeperOptionsFlow(config_entry)


class GatekeeperOptionsFlow(OptionsFlowWithConfigEntry):
    """Handle options flow for Gatekeeper HA."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        "guest_port",
                        default=current.get("guest_port", DEFAULT_GUEST_PAGE_PORT),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1024, max=65535)),
                    vol.Optional(
                        "default_expiry_hours",
                        default=current.get("default_expiry_hours", DEFAULT_EXPIRY_HOURS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=8760)),
                    vol.Optional(
                        "default_auto_disable_hours",
                        default=current.get("default_auto_disable_hours", DEFAULT_AUTO_DISABLE_HOURS),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8760)),
                    vol.Optional(
                        "default_guest_mode_duration_hours",
                        default=current.get("default_guest_mode_duration_hours", 48),
                    ): vol.All(vol.Coerce(int), vol.Range(min=0, max=8760)),
                }
            ),
            last_step=True,
        )
