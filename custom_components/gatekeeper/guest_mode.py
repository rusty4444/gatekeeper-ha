"""Guest mode state machine for Gatekeeper HA."""

from __future__ import annotations

import asyncio
import copy
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import *
from .token_manager import TokenManager

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_MODE = f"{DOMAIN}.mode"
STORAGE_KEY_SNAPSHOT = f"{DOMAIN}.snapshot"


class GuestModeManager:
    """Manages guest mode state: automation snapshots, safe states, expiry."""

    def __init__(self, hass: HomeAssistant, token_manager: TokenManager) -> None:
        self.hass = hass
        self._token_manager = token_manager
        self._mode_store = Store(hass, 1, STORAGE_KEY_MODE)
        self._snapshot_store = Store(hass, 1, STORAGE_KEY_SNAPSHOT)
        self._state: str = MODE_OFF
        self._auto_disable_at: datetime | None = None
        self._auto_disable_task: asyncio.Task | None = None

    async def async_load(self) -> None:
        """Load persisted state."""
        data = await self._mode_store.async_load()
        if data:
            self._state = data.get("state", MODE_OFF)
            auto_disable = data.get("auto_disable_at")
            if auto_disable:
                try:
                    self._auto_disable_at = datetime.fromisoformat(auto_disable)
                except (ValueError, TypeError):
                    self._auto_disable_at = None

            if self._state == MODE_ON:
                _LOGGER.info("Guest mode was ON — scheduling auto-disable at %s", self._auto_disable_at)
                await self._schedule_auto_disable()

    async def async_activate(
        self,
        auto_disable_hours: float = 0,
        disable_automations: bool = True,
        automation_entity_ids: list[str] | None = None,
        set_safe_states: bool = True,
    ) -> None:
        """Activate guest mode.

        Steps:
        1. Snapshot current state of targeted automations
        2. Disable selected automations
        3. Optionally set entities to safe states
        4. Schedule auto-disable if configured
        """
        if self._state == MODE_ON:
            _LOGGER.warning("Guest mode is already active — re-activating")
            await self._cancel_auto_disable()

        self._state = MODE_ON

        if disable_automations:
            await self._snapshot_and_disable_automations(automation_entity_ids)

        if set_safe_states:
            await self._set_safe_states()

        # Auto-disable scheduling
        if auto_disable_hours > 0:
            self._auto_disable_at = datetime.now(timezone.utc) + timedelta(hours=auto_disable_hours)
            await self._schedule_auto_disable()
        else:
            self._auto_disable_at = None

        await self._persist_state()
        _LOGGER.info("Guest mode activated (auto-disable: %s)", self._auto_disable_at or "manual")

    async def async_deactivate(self) -> None:
        """Deactivate guest mode.

        Steps:
        1. Cancel auto-disable timer
        2. Restore automations from snapshot
        3. Revoke all active tokens
        4. Persist state
        """
        self._state = MODE_OFF
        await self._cancel_auto_disable()
        self._auto_disable_at = None
        await self._restore_automations()
        await self._clear_snapshot()
        await self._token_manager.async_revoke_all()
        await self._persist_state()
        _LOGGER.info("Guest mode deactivated")

    @property
    def is_active(self) -> bool:
        return self._state == MODE_ON

    @property
    def state(self) -> str:
        return self._state

    @property
    def remaining_seconds(self) -> float | None:
        if self._auto_disable_at is None:
            return None
        remaining = (self._auto_disable_at - datetime.now(timezone.utc)).total_seconds()
        return max(0.0, remaining)

    async def _snapshot_and_disable_automations(
        self, automation_entity_ids: list[str] | None = None
    ) -> None:
        """Snapshot current automation states and disable them."""
        domain = "automation"
        states = self.hass.states

        if automation_entity_ids:
            target_ids = automation_entity_ids
        else:
            # All automations
            target_ids = [
                e.entity_id for e in states.async_all(domain)
            ]

        snapshot = {}
        for entity_id in target_ids:
            state = states.get(entity_id)
            if state is not None:
                snapshot[entity_id] = state.state

        if not snapshot:
            _LOGGER.debug("No automations to snapshot")
            return

        # Save snapshot
        await self._snapshot_store.async_save({
            "automations": snapshot,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        })

        # Disable automations
        disabled_count = 0
        for entity_id in snapshot:
            try:
                await self.hass.services.async_call(
                    domain, "turn_off",
                    {"entity_id": entity_id},
                    blocking=True,
                )
                disabled_count += 1
            except Exception as exc:
                _LOGGER.warning("Failed to disable automation %s: %s", entity_id, exc)

        _LOGGER.info("Disabled %d automations for guest mode", disabled_count)

    async def _restore_automations(self) -> None:
        """Restore automations from snapshot."""
        data = await self._snapshot_store.async_load()
        if not data or "automations" not in data:
            _LOGGER.debug("No automation snapshot to restore")
            return

        restored_count = 0
        for entity_id, previous_state in data["automations"].items():
            if previous_state == "on":
                try:
                    await self.hass.services.async_call(
                        "automation", "turn_on",
                        {"entity_id": entity_id},
                        blocking=True,
                    )
                    restored_count += 1
                except Exception as exc:
                    _LOGGER.warning("Failed to restore automation %s: %s", entity_id, exc)

        _LOGGER.info("Restored %d automations", restored_count)

    async def _clear_snapshot(self) -> None:
        """Remove stored snapshot."""
        await self._snapshot_store.async_save({"automations": {}, "captured_at": None})

    async def _set_safe_states(self) -> None:
        """Set entities to safe default states for guests."""
        # User-configurable safe states — for now, just log
        _LOGGER.debug("Safe state application not yet configured — skipping")

    async def _persist_state(self) -> None:
        """Persist current mode state."""
        await self._mode_store.async_save({
            "state": self._state,
            "auto_disable_at": self._auto_disable_at.isoformat() if self._auto_disable_at else None,
        })

    async def _schedule_auto_disable(self) -> None:
        """Schedule auto-disable via a delayed task."""
        if self._auto_disable_at is None:
            return

        await self._cancel_auto_disable()

        now = datetime.now(timezone.utc)
        delay = (self._auto_disable_at - now).total_seconds()
        if delay <= 0:
            await self.async_deactivate()
            return

        async def _auto_disable():
            await asyncio.sleep(delay)
            _LOGGER.info("Auto-disable timer triggered — deactivating guest mode")
            await self.async_deactivate()

        self._auto_disable_task = asyncio.create_task(_auto_disable())

    async def _cancel_auto_disable(self) -> None:
        """Cancel pending auto-disable task."""
        if self._auto_disable_task is not None:
            self._auto_disable_task.cancel()
            self._auto_disable_task = None
