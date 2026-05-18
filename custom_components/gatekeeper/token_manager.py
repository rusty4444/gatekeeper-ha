"""Token management for Gatekeeper HA."""

from __future__ import annotations

import asyncio
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    BCRYPT_ROUNDS,
    STORAGE_KEY,
    STORAGE_VERSION,
    TOKEN_BYTE_LENGTH,
    TOKEN_ID_LENGTH,
    TOKEN_SOURCE_MANUAL,
)

_LOGGER = logging.getLogger(__name__)

TOKEN_SCHEMA_VERSION = 1


class TokenManager:
    """Manages guest access tokens with persistent storage."""

    def __init__(self, hass: HomeAssistant) -> None:
        self.hass = hass
        self._store = Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._tokens: dict[str, dict[str, Any]] = {}
        self._lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load tokens from persistent storage."""
        data = await self._store.async_load()
        if data and isinstance(data, dict):
            self._tokens = data.get("tokens", {})
            _LOGGER.info("Loaded %d tokens from storage", len(self._tokens))
        else:
            self._tokens = {}
        await self._purge_expired()

    async def _async_save(self) -> None:
        """Persist tokens to storage."""
        await self._store.async_save({"tokens": self._tokens, "schema": TOKEN_SCHEMA_VERSION})

    async def async_create_token(
        self,
        label: str = "Guest",
        duration_hours: float = 24,
        scoped_entities: list[str] | None = None,
        scoped_domains: list[str] | None = None,
        allowed_services: list[str] | None = None,
        max_uses: int = 0,
        show_wifi: bool = False,
        source: str = TOKEN_SOURCE_MANUAL,
    ) -> dict[str, Any]:
        """Create a new guest token.

        Returns the full safe-token dict plus the one-time ``_secret`` and a
        path-only ``guest_url``. The hash is never returned; the secret is
        returned exactly once and never persisted.
        """
        if scoped_entities is None:
            scoped_entities = ["light.*"]
        if scoped_domains is None:
            scoped_domains = ["light", "switch"]

        token_id = self._generate_token_id()
        token_secret = secrets.token_urlsafe(TOKEN_BYTE_LENGTH)
        token_hash = self._hash_secret(token_secret)

        expires_at = (
            datetime.now(timezone.utc) + timedelta(hours=duration_hours)
        ).isoformat()

        token: dict[str, Any] = {
            "token_id": token_id,
            "token_hash": token_hash,
            "label": label,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": expires_at,
            "max_uses": max_uses,
            "use_count": 0,
            "is_active": True,
            "scoped_entities": scoped_entities,
            "scoped_domains": scoped_domains,
            "allowed_services": allowed_services or [],
            "show_wifi": bool(show_wifi),
            "source": source,
        }

        async with self._lock:
            self._tokens[token_id] = token
            await self._async_save()

        _LOGGER.info(
            "Created token '%s' (ID: %s, source: %s) expiring at %s",
            label, token_id, source, expires_at,
        )

        safe = self._safe_token(token)
        safe["_secret"] = token_secret
        safe["guest_url"] = self._build_guest_url(token_id, token_secret)
        return safe

    async def async_revoke_token(self, token_id: str) -> bool:
        """Revoke a token by ID."""
        async with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                _LOGGER.warning("Attempted to revoke unknown token: %s", token_id)
                return False
            token["is_active"] = False
            await self._async_save()
        _LOGGER.info("Revoked token: %s ('%s')", token_id, token.get("label", ""))
        return True

    async def async_revoke_all(self, source: str | None = None) -> int:
        """Revoke active tokens.

        When ``source`` is provided, only tokens with a matching ``source``
        field are revoked. When ``source`` is None, all active tokens are
        revoked (used by manual/admin actions only).
        """
        count = 0
        async with self._lock:
            for token in self._tokens.values():
                if not token.get("is_active", False):
                    continue
                if source is not None and token.get("source") != source:
                    continue
                token["is_active"] = False
                count += 1
            if count:
                await self._async_save()
        return count

    async def async_validate_token(
        self,
        token_id: str,
        token_secret: str,
        *,
        count_use: bool = True,
    ) -> dict[str, Any] | None:
        """Validate a token by ID and secret.

        Returns a safe token dict (no hash) if valid, None otherwise. The
        full read-modify-write critical section runs under ``self._lock``
        so concurrent requests cannot race past max_uses or revocation.
        """
        async with self._lock:
            token = self._tokens.get(token_id)
            if token is None:
                _LOGGER.warning("Token validation failed: unknown ID %s", token_id)
                return None

            if not token.get("is_active", False):
                _LOGGER.warning("Token validation failed: token %s is inactive", token_id)
                return None

            if not self._verify_secret(token_secret, token.get("token_hash", "")):
                _LOGGER.warning("Token validation failed: invalid secret for %s", token_id)
                return None

            expires_at = token.get("expires_at")
            if expires_at:
                try:
                    expires_dt = datetime.fromisoformat(expires_at)
                    if expires_dt < datetime.now(timezone.utc):
                        _LOGGER.info("Token %s has expired", token_id)
                        token["is_active"] = False
                        await self._async_save()
                        return None
                except (ValueError, TypeError):
                    _LOGGER.warning("Token %s has invalid expires_at: %s", token_id, expires_at)
                    return None

            max_uses = token.get("max_uses", 0)
            current = token.get("use_count", 0)
            if max_uses > 0 and current >= max_uses:
                _LOGGER.info("Token %s has exhausted its use limit (%d)", token_id, max_uses)
                token["is_active"] = False
                await self._async_save()
                return None

            if count_use:
                token["use_count"] = current + 1
                await self._async_save()

            return self._safe_token(token)

    async def async_list_active(self) -> list[dict[str, Any]]:
        """List all active tokens (safe version, no secret/hash)."""
        await self._purge_expired()
        return [
            self._safe_token(t) for t in self._tokens.values()
            if t.get("is_active", False)
        ]

    async def async_get_token(self, token_id: str) -> dict[str, Any] | None:
        """Get a single token by ID (safe version)."""
        token = self._tokens.get(token_id)
        if token is None:
            return None
        return self._safe_token(token)

    async def _purge_expired(self) -> None:
        """Mark expired tokens as inactive."""
        now = datetime.now(timezone.utc)
        changed = False
        for token in self._tokens.values():
            if not token.get("is_active", False):
                continue
            expires_at = token.get("expires_at")
            if expires_at:
                try:
                    if datetime.fromisoformat(expires_at) < now:
                        token["is_active"] = False
                        changed = True
                except (ValueError, TypeError):
                    pass
        if changed:
            await self._async_save()

    @staticmethod
    def _generate_token_id() -> str:
        """Generate a short unique token ID."""
        return "gk_" + secrets.token_urlsafe(TOKEN_ID_LENGTH)

    @staticmethod
    def _build_guest_url(
        token_id: str, token_secret: str, base_url: str | None = None
    ) -> str:
        """Build the guest access URL for a token. Never stored — computed on demand.

        If ``base_url`` is provided, return an absolute URL; otherwise return
        a path-only URL. The proxy server is what actually builds absolute
        URLs because it knows the guest-page host/port.
        """
        path = f"/gatekeeper/guest/{token_id}/{token_secret}"
        if base_url:
            return f"{base_url.rstrip('/')}{path}"
        return path

    @staticmethod
    def _hash_secret(secret: str) -> str:
        """Hash a token secret using bcrypt.

        bcrypt is a hard requirement declared in manifest.json; there is no
        fallback. If bcrypt fails to import the integration won't load at all.
        """
        return bcrypt.hashpw(
            secret.encode("utf-8"), bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
        ).decode("utf-8")

    @staticmethod
    def _verify_secret(secret: str, token_hash: str) -> bool:
        """Verify a secret against its stored bcrypt hash (constant-time)."""
        if not token_hash or not token_hash.startswith("$2"):
            return False
        try:
            return bcrypt.checkpw(secret.encode("utf-8"), token_hash.encode("utf-8"))
        except Exception:
            return False

    @staticmethod
    def _safe_token(token: dict[str, Any]) -> dict[str, Any]:
        """Return a token dict with the secret hash removed.

        Includes scope, source, show_wifi, and timing information needed by
        the proxy to enforce access. Only ``token_hash`` is excluded.
        """
        return {k: v for k, v in token.items() if k != "token_hash"}
