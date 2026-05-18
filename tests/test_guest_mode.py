"""Tests for Gatekeeper HA — Guest Mode Manager."""

from __future__ import annotations

import pytest

from custom_components.gatekeeper.const import MODE_OFF, MODE_ON
from custom_components.gatekeeper.guest_mode import GuestModeManager
from custom_components.gatekeeper.token_manager import TokenManager


@pytest.mark.asyncio
async def test_initial_state_is_off(hass):
    """Test guest mode starts as OFF."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    assert guest_mgr.state == MODE_OFF
    assert guest_mgr.is_active is False


@pytest.mark.asyncio
async def test_activate_mode(hass):
    """Test activating guest mode."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await guest_mgr.async_activate()
    assert guest_mgr.state == MODE_ON
    assert guest_mgr.is_active is True


@pytest.mark.asyncio
async def test_deactivate_mode(hass):
    """Test deactivating guest mode."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await guest_mgr.async_activate()
    await guest_mgr.async_deactivate()

    assert guest_mgr.state == MODE_OFF
    assert guest_mgr.is_active is False


@pytest.mark.asyncio
async def test_auto_disable(hass):
    """Test auto-disable timer."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    # Activate with 0.001 hours (~3.6 seconds) auto-disable
    await guest_mgr.async_activate(auto_disable_hours=0.001)
    assert guest_mgr.is_active is True

    remaining = guest_mgr.remaining_seconds
    assert remaining is not None
    assert remaining > 0

    # async_shutdown must cancel the timer so the HA fixture doesn't
    # complain about lingering handles.
    await guest_mgr.async_shutdown()


@pytest.mark.asyncio
async def test_async_shutdown_cancels_timer(hass):
    """async_shutdown must cancel an active auto-disable timer."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await guest_mgr.async_activate(auto_disable_hours=1.0)
    assert guest_mgr._auto_disable_unsub is not None

    await guest_mgr.async_shutdown()
    assert guest_mgr._auto_disable_unsub is None


@pytest.mark.asyncio
async def test_auto_disable_zero_is_manual(hass):
    """Test 0 hours means no auto-disable timer."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await guest_mgr.async_activate(auto_disable_hours=0)
    assert guest_mgr.remaining_seconds is None


@pytest.mark.asyncio
async def test_deactivate_revokes_only_guest_mode_tokens(hass):
    """Deactivate revokes tokens whose source is guest_mode and leaves manual tokens alone.

    Previously deactivate revoked every token in the system, which clobbered
    admin-issued tokens unrelated to guest mode. Source-scoped revocation
    keeps manual tokens active across guest-mode cycles.
    """
    from custom_components.gatekeeper.const import (
        TOKEN_SOURCE_GUEST_MODE,
        TOKEN_SOURCE_MANUAL,
    )

    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    manual_a = await token_mgr.async_create_token(
        label="Manual", source=TOKEN_SOURCE_MANUAL,
    )
    guest_token = await token_mgr.async_create_token(
        label="GuestModeToken", source=TOKEN_SOURCE_GUEST_MODE,
    )

    await guest_mgr.async_activate()
    await guest_mgr.async_deactivate()

    active_ids = {t["token_id"] for t in await token_mgr.async_list_active()}
    assert manual_a["token_id"] in active_ids
    assert guest_token["token_id"] not in active_ids


@pytest.mark.asyncio
async def test_state_persistence(hass):
    """Test guest mode state survives reload."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await guest_mgr.async_activate(auto_disable_hours=48)

    # Simulate restart
    token_mgr2 = TokenManager(hass)
    await token_mgr2.async_load()
    guest_mgr2 = GuestModeManager(hass, token_mgr2)
    await guest_mgr2.async_load()

    assert guest_mgr2.state == MODE_ON
    assert guest_mgr2.is_active is True

    # Tear down both timers so HA's lingering-timer check passes.
    await guest_mgr.async_shutdown()
    await guest_mgr2.async_shutdown()
