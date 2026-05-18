"""Tests for safe-state override translation in GuestModeManager.

The bug fixed here: previously the override path passed the *state* value
(``on``/``off``/``locked``) directly as the service name, producing calls
like ``light.on`` which is not a real service. The fix maps states to the
canonical service (``turn_on``, ``turn_off``, ``lock``, ...).
"""

from __future__ import annotations

import pytest

from custom_components.gatekeeper.guest_mode import GuestModeManager
from custom_components.gatekeeper.token_manager import TokenManager


def _install_service_capture(hass) -> list[tuple[str, str, dict]]:
    """Register a no-op handler for every (domain, service) we expect.

    HA's ServiceRegistry is read-only, so we can't monkey-patch
    ``async_call`` directly. Instead we register matching services with a
    capture list. Anything calling ``hass.services.async_call`` for one of
    these (domain, service) pairs is recorded.
    """
    captured: list[tuple[str, str, dict]] = []

    async def _handler(call):
        captured.append((call.domain, call.service, dict(call.data)))

    for domain, service in [
        ("light", "turn_on"),
        ("light", "turn_off"),
        ("lock", "lock"),
        ("cover", "close_cover"),
    ]:
        hass.services.async_register(domain, service, _handler)
    return captured


@pytest.mark.asyncio
async def test_safe_state_override_maps_on_to_turn_on(hass):
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    captured = _install_service_capture(hass)

    await guest_mgr._set_safe_states({
        "light.kitchen": {"state": "on", "brightness": 50},
        "light.hall": {"state": "off"},
        "lock.front": {"state": "locked"},
        "cover.garage": {"state": "closed"},
    })
    await hass.async_block_till_done()

    services_called = {(d, s): data for d, s, data in captured}
    assert ("light", "turn_on") in services_called
    assert services_called[("light", "turn_on")] == {
        "entity_id": "light.kitchen", "brightness": 50,
    }
    assert ("light", "turn_off") in services_called
    assert ("lock", "lock") in services_called
    assert ("cover", "close_cover") in services_called


@pytest.mark.asyncio
async def test_safe_state_without_overrides_does_nothing(hass):
    """Without overrides, no entities should be touched."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    captured = _install_service_capture(hass)

    # No overrides means no blanket sweep of every domain. Previously the
    # function iterated every entity in lock/cover/climate/fan/switch.
    await guest_mgr._set_safe_states(None)
    await hass.async_block_till_done()
    assert captured == []
