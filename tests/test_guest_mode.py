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
async def test_revoke_all_tokens_on_deactivate(hass):
    """Test that deactivate_mode revokes all tokens."""
    token_mgr = TokenManager(hass)
    await token_mgr.async_load()
    guest_mgr = GuestModeManager(hass, token_mgr)
    await guest_mgr.async_load()

    await token_mgr.async_create_token(label="GuestToken")
    await token_mgr.async_create_token(label="GuestToken2")

    await guest_mgr.async_activate()
    await guest_mgr.async_deactivate()

    active_tokens = await token_mgr.async_list_active()
    assert len(active_tokens) == 0


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
