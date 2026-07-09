"""Config flow for Gatekeeper HA."""

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    DEFAULT_AUTO_DISABLE_HOURS,
    DEFAULT_EXPIRY_HOURS,
    DEFAULT_GUEST_PAGE_PORT,
    DOMAIN,
    OPT_DISABLE_AUTOMATIONS,
    OPT_DISABLE_SCENES,
    OPT_DISABLE_SCRIPTS,
    OPT_PUBLIC_GUEST_BASE_URL,
    OPT_SET_SAFE_STATES,
)

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


def _normalize_public_guest_base_url(value: Any) -> str:
    """Validate and normalize the public guest base URL option."""
    if value is None:
        return ""
    if not isinstance(value, str):
        raise vol.Invalid("invalid_url")

    value = value.strip()
    if not value:
        return ""

    try:
        parsed = urlparse(value)
        hostname = parsed.hostname
        _ = parsed.port
    except ValueError as err:
        raise vol.Invalid("invalid_url") from err

    if (
        parsed.scheme.lower() not in ("http", "https")
        or not parsed.netloc
        or not hostname
        or parsed.params
        or parsed.query
        or parsed.fragment
        or any(char.isspace() for char in value)
    ):
        raise vol.Invalid("invalid_url")

    return value.rstrip("/")


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

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow."""
        return GatekeeperOptionsFlow()


class GatekeeperOptionsFlow(OptionsFlow):
    """Handle options flow for Gatekeeper HA.

    Note: `self.config_entry` is provided automatically by the base class
    in HA 2024.12+. Do not store it manually.
    """

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}
        if user_input is not None:
            options = {**user_input}
            try:
                options[OPT_PUBLIC_GUEST_BASE_URL] = _normalize_public_guest_base_url(
                    options.get(OPT_PUBLIC_GUEST_BASE_URL, "")
                )
            except vol.Invalid:
                errors[OPT_PUBLIC_GUEST_BASE_URL] = "invalid_url"
            else:
                return self.async_create_entry(title="", data=options)

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
                        OPT_PUBLIC_GUEST_BASE_URL,
                        default=current.get(OPT_PUBLIC_GUEST_BASE_URL, ""),
                    ): _normalize_public_guest_base_url,
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
                    vol.Optional(
                        "disable_automations_on_mode",
                        default=current.get(OPT_DISABLE_AUTOMATIONS, False),
                    ): cv.boolean,
                    vol.Optional(
                        "disable_scripts_on_mode",
                        default=current.get(OPT_DISABLE_SCRIPTS, True),
                    ): cv.boolean,
                    vol.Optional(
                        "disable_scenes_on_mode",
                        default=current.get(OPT_DISABLE_SCENES, True),
                    ): cv.boolean,
                    vol.Optional(
                        "apply_safe_states",
                        default=current.get(OPT_SET_SAFE_STATES, True),
                    ): cv.boolean,
                    vol.Optional(
                        "wifi_ssid",
                        default=current.get("wifi_ssid", ""),
                    ): cv.string,
                    vol.Optional(
                        "wifi_password",
                        default=current.get("wifi_password", ""),
                    ): cv.string,
                    vol.Optional(
                        "show_wifi",
                        default=current.get("show_wifi", False),
                    ): cv.boolean,
                }
            ),
            errors=errors,
            last_step=True,
        )
