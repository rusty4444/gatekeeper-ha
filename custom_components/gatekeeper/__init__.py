"""Core setup for Gatekeeper HA integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STOP, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

from .const import *
from .token_manager import TokenManager
from .guest_mode import GuestModeManager
from .auth_proxy import AuthProxyServer

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = []


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Gatekeeper from YAML (not used — config flow only)."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Gatekeeper from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # Init token manager (persistent storage)
    token_manager = TokenManager(hass)
    await token_manager.async_load()
    hass.data[DOMAIN]["token_manager"] = token_manager

    # Init guest mode manager
    guest_mode = GuestModeManager(hass, token_manager)
    await guest_mode.async_load()
    hass.data[DOMAIN]["guest_mode"] = guest_mode

    # Init auth proxy server
    proxy_port = entry.options.get("guest_port", DEFAULT_GUEST_PAGE_PORT)
    auth_proxy = AuthProxyServer(hass, token_manager, port=proxy_port)
    hass.data[DOMAIN]["auth_proxy"] = auth_proxy

    # Register services
    _register_services(hass, token_manager, guest_mode)

    # Start auth proxy when HA is fully started
    async def _start_proxy(_event=None):
        await auth_proxy.async_start()

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, auth_proxy.async_stop)

    if hass.is_running:
        hass.async_create_task(_start_proxy())
    else:
        hass.bus.async_listen_once("homeassistant_started", _start_proxy)

    entry.async_on_unload(entry.add_update_listener(_update_listener))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Gatekeeper."""
    auth_proxy: AuthProxyServer | None = hass.data.get(DOMAIN, {}).get("auth_proxy")
    if auth_proxy:
        await auth_proxy.async_stop()

    hass.data.pop(DOMAIN, None)
    return True


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry version."""
    _LOGGER.debug("Migrating config entry from version %s", entry.version)
    return True


async def _update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle config entry options update."""
    await hass.config_entries.async_reload(entry.entry_id)


def _register_services(
    hass: HomeAssistant,
    token_manager: TokenManager,
    guest_mode: GuestModeManager,
) -> None:
    """Register HA services (supports_response=True for data-returning services)."""

    async def _handle_create_token(call: ServiceCall) -> dict[str, Any]:
        label = call.data.get(ATTR_LABEL, "Guest")
        duration = call.data.get(ATTR_DURATION, DEFAULT_EXPIRY_HOURS)
        scoped_entities = call.data.get(ATTR_SCOPED_ENTITIES, ["light.*"])
        scoped_domains = call.data.get(ATTR_SCOPED_DOMAINS, ["light", "switch"])
        allowed_services = call.data.get(ATTR_ALLOWED_SERVICES, None)
        max_uses = call.data.get(ATTR_MAX_USES, 0)

        token = await token_manager.async_create_token(
            label=label,
            duration_hours=duration,
            scoped_entities=scoped_entities,
            scoped_domains=scoped_domains,
            allowed_services=allowed_services,
            max_uses=max_uses,
        )
        hass.bus.async_fire(EVENT_TOKEN_CREATED, {"token_id": token["token_id"], "label": label})

        return {
            "token_id": token["token_id"],
            "secret": token["_secret"],
            "guest_url": token["guest_url"],
            "expires_at": token["expires_at"],
        }

    async def _handle_revoke_token(call: ServiceCall) -> dict[str, bool]:
        token_id = call.data[ATTR_TOKEN_ID]
        await token_manager.async_revoke_token(token_id)
        hass.bus.async_fire(EVENT_TOKEN_REVOKED, {"token_id": token_id})
        return {"success": True}

    async def _handle_activate_mode(call: ServiceCall) -> dict[str, bool]:
        auto_disable = call.data.get(ATTR_AUTO_DISABLE_AFTER, 0)
        disable_automations = call.data.get(ATTR_DISABLE_AUTOMATIONS, True)
        automation_ids = call.data.get(ATTR_AUTOMATION_ENTITY_IDS, None)
        set_safe_states = call.data.get(ATTR_SET_SAFE_STATES, True)

        await guest_mode.async_activate(
            auto_disable_hours=auto_disable,
            disable_automations=disable_automations,
            automation_entity_ids=automation_ids,
            set_safe_states=set_safe_states,
        )
        hass.bus.async_fire(EVENT_MODE_STARTED, {})
        return {"success": True}

    async def _handle_deactivate_mode(call: ServiceCall) -> dict[str, bool]:
        await guest_mode.async_deactivate()
        hass.bus.async_fire(EVENT_MODE_ENDED, {})
        return {"success": True}

    async def _handle_get_tokens(call: ServiceCall) -> dict[str, list]:
        tokens = await token_manager.async_list_active()
        return {"tokens": tokens}

    async def _handle_get_guest_url(call: ServiceCall) -> dict[str, str | None]:
        proxy: AuthProxyServer | None = hass.data.get(DOMAIN, {}).get("auth_proxy")
        url = proxy.external_url if (proxy and proxy.external_url) else None
        return {"url": url}

    # Register all services with supports_response where applicable
    hass.services.async_register(
        DOMAIN, SERVICE_CREATE_TOKEN, _handle_create_token,
        schema=vol.Schema({
            vol.Optional(ATTR_LABEL, default="Guest"): cv.string,
            vol.Optional(ATTR_DURATION, default=DEFAULT_EXPIRY_HOURS): vol.Coerce(int),
            vol.Optional(ATTR_SCOPED_ENTITIES, default=["light.*"]): vol.Any(cv.ensure_list, None),
            vol.Optional(ATTR_SCOPED_DOMAINS, default=["light", "switch"]): vol.Any(cv.ensure_list, None),
            vol.Optional(ATTR_ALLOWED_SERVICES): vol.Any(cv.ensure_list, None),
            vol.Optional(ATTR_MAX_USES, default=0): vol.Coerce(int),
        }),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_REVOKE_TOKEN, _handle_revoke_token,
        schema=vol.Schema({vol.Required(ATTR_TOKEN_ID): cv.string}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_ACTIVATE_MODE, _handle_activate_mode,
        schema=vol.Schema({
            vol.Optional(ATTR_AUTO_DISABLE_AFTER, default=0): vol.Coerce(int),
            vol.Optional(ATTR_DISABLE_AUTOMATIONS, default=True): cv.boolean,
            vol.Optional(ATTR_AUTOMATION_ENTITY_IDS): vol.Any(cv.ensure_list, None),
            vol.Optional(ATTR_SET_SAFE_STATES, default=True): cv.boolean,
        }),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_DEACTIVATE_MODE, _handle_deactivate_mode,
        schema=vol.Schema({}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_GET_TOKENS, _handle_get_tokens,
        schema=vol.Schema({}),
        supports_response=True,
    )

    hass.services.async_register(
        DOMAIN, SERVICE_GET_GUEST_URL, _handle_get_guest_url,
        schema=vol.Schema({}),
        supports_response=True,
    )
