"""Tests for Gatekeeper HA — Token Manager."""

from __future__ import annotations

import pytest

from custom_components.gatekeeper.token_manager import TokenManager


@pytest.mark.asyncio
async def test_create_token_returns_expected_fields(hass):
    """Test that create_token returns token_id, secret, and guest_url."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(label="Test", duration_hours=24)

    assert "token_id" in token
    assert token["token_id"].startswith("gk_")
    assert "_secret" in token
    assert len(token["_secret"]) > 20
    assert "guest_url" in token
    assert token["label"] == "Test"
    assert token["is_active"] is True


@pytest.mark.asyncio
async def test_token_default_scope(hass):
    """Test default scopes are set correctly."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token()
    assert "light.*" in token["scoped_entities"]
    assert "light" in token["scoped_domains"]


@pytest.mark.asyncio
async def test_token_expiry(hass):
    """Test token expires and becomes inactive."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    # Create token that expires very soon (0 hours = now)
    import time
    token = await mgr.async_create_token(duration_hours=0)
    assert token["is_active"] is True

    # Validate with correct secret — should fail due to expiry
    result = await mgr.async_validate_token(token["token_id"], token["_secret"])
    assert result is None

    # Should be marked inactive now
    stored = await mgr.async_get_token(token["token_id"])
    assert stored is not None
    assert stored["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_token(hass):
    """Test token revocation."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(label="RevokeMe")
    result = await mgr.async_revoke_token(token["token_id"])
    assert result is True

    stored = await mgr.async_get_token(token["token_id"])
    assert stored["is_active"] is False


@pytest.mark.asyncio
async def test_revoke_nonexistent_token(hass):
    """Test revoking a token that doesn't exist."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    result = await mgr.async_revoke_token("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_validate_token_wrong_secret(hass):
    """Test validation fails with wrong secret."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token()
    result = await mgr.async_validate_token(token["token_id"], "wrong-secret")
    assert result is None


@pytest.mark.asyncio
async def test_validate_token_success(hass):
    """Test successful token validation returns safe token data."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(duration_hours=48)
    result = await mgr.async_validate_token(token["token_id"], token["_secret"])

    assert result is not None
    assert result["token_id"] == token["token_id"]
    assert "token_hash" not in result
    assert "_secret" not in result
    assert result["is_active"] is True


@pytest.mark.asyncio
async def test_use_count_increments(hass):
    """Test use_count increments on validation."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(duration_hours=48)
    secret = token["_secret"]
    token_id = token["token_id"]

    await mgr.async_validate_token(token_id, secret)
    await mgr.async_validate_token(token_id, secret)

    stored = await mgr.async_get_token(token_id)
    assert stored["use_count"] >= 2


@pytest.mark.asyncio
async def test_max_uses_exhausted(hass):
    """Test token deactivates when max_uses is reached."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(duration_hours=48, max_uses=2)
    secret = token["_secret"]
    token_id = token["token_id"]

    # Use it 2 times
    assert await mgr.async_validate_token(token_id, secret) is not None
    assert await mgr.async_validate_token(token_id, secret) is not None

    # 3rd use should fail
    assert await mgr.async_validate_token(token_id, secret) is None


@pytest.mark.asyncio
async def test_list_active(hass):
    """Test listing active tokens."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    await mgr.async_create_token(label="Token A", duration_hours=24)
    token_b = await mgr.async_create_token(label="Token B", duration_hours=24)

    await mgr.async_revoke_token(token_b["token_id"])

    active = await mgr.async_list_active()
    labels = [t["label"] for t in active]

    assert "Token A" in labels
    assert "Token B" not in labels


@pytest.mark.asyncio
async def test_revoke_all(hass):
    """Test revoking all active tokens."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    await mgr.async_create_token(label="A")
    await mgr.async_create_token(label="B")
    await mgr.async_create_token(label="C")

    count = await mgr.async_revoke_all()
    assert count == 3

    active = await mgr.async_list_active()
    assert len(active) == 0


@pytest.mark.asyncio
async def test_storage_persists_tokens(hass):
    """Test tokens survive async_load round-trip."""
    mgr = TokenManager(hass)
    await mgr.async_load()

    token = await mgr.async_create_token(label="Persist", duration_hours=24)
    token_id = token["token_id"]

    # Create new manager instance (simulates restart)
    mgr2 = TokenManager(hass)
    await mgr2.async_load()

    stored = await mgr2.async_get_token(token_id)
    assert stored is not None
    assert stored["label"] == "Persist"
    assert stored["is_active"] is True
