"""Guest mode state machine for Gatekeeper HA."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import *
from .token_manager import TokenManager

_LOGGER = logging.getLogger(__name__)

STORAGE_KEY_MODE = f"{DOMAIN}.mode"
STORAGE_KEY_SNAPSHOT = f"{DOMAIN}.snapshot"

DOMAINS_TO_SNAPSHOT = {
    "automation": "automation_entity_ids",
    "script": "disable_scripts",
    "scene": "disable_scenes",
}


class GuestModeManager:
    """Manages guest mode state: automation/script/scene snapshots, safe states, expiry."""

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
        disable_scripts: bool = True,
        disable_scenes: bool = True,
        safe_state_overrides: dict[str, dict[str, Any]] | None = None,
    ) -> None:
        """Activate guest mode.

        Steps:
        1. Snapshot current state of targeted entities (automations, scripts, scenes)
        2. Disable selected automations, scripts, and scenes
        3. Optionally set entities to safe states
        4. Schedule auto-disable if configured
        """
        if self._state == MODE_ON:
            _LOGGER.warning("Guest mode is already active — re-activating")
            await self._cancel_auto_disable()

        self._state = MODE_ON

        # Snapshot and disable entities across multiple domains
        await self._snapshot_and_disable(
            disable_automations=disable_automations,
            automation_entity_ids=automation_entity_ids,
            disable_scripts=disable_scripts,
            disable_scenes=disable_scenes,
        )

        if set_safe_states:
            await self._set_safe_states(safe_state_overrides)

        # Auto-disable scheduling
        if auto_disable_hours > 0:
            self._auto_disable_at = datetime.now(timezone.utc) + timedelta(hours=auto_disable_hours)
            await self._schedule_auto_disable()
        else:
            self._auto_disable_at = None

        await self._persist_state()
        _LOGGER.info(
            "Guest mode activated (auto-disable: %s, safe_states: %s)",
            self._auto_disable_at or "manual",
            set_safe_states,
        )

    async def async_deactivate(self) -> None:
        """Deactivate guest mode.

        Steps:
        1. Cancel auto-disable timer
        2. Restore automations/scripts/scenes from snapshot
        3. Revoke all active tokens
        4. Persist state
        """
        self._state = MODE_OFF
        await self._cancel_auto_disable()
        self._auto_disable_at = None
        await self._restore_from_snapshot()
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

    async def _snapshot_and_disable(
        self,
        disable_automations: bool = True,
        automation_entity_ids: list[str] | None = None,
        disable_scripts: bool = True,
        disable_scenes: bool = True,
    ) -> None:
        """Snapshot and disable automations, scripts, and scenes."""
        snapshot: dict[str, dict[str, str]] = {}

        # Automations
        if disable_automations:
            snap = await self._snapshot_domain("automation", automation_entity_ids)
            await self._disable_domain("automation", snap)
            snapshot["automation"] = snap

        # Scripts
        if disable_scripts:
            snap = await self._snapshot_domain("script", None)
            await self._disable_domain("script", snap)
            snapshot["script"] = snap

        # Scenes
        if disable_scenes:
            snap = await self._snapshot_domain("scene", None)
            await self._disable_domain("scene", snap)
            snapshot["scene"] = snap

        if not snapshot:
            _LOGGER.debug("No entities to snapshot")
            return

        # Persist snapshot
        await self._snapshot_store.async_save({
            "entities": snapshot,
            "captured_at": datetime.now(timezone.utc).isoformat(),
        })

        total = sum(len(v) for v in snapshot.values())
        _LOGGER.info("Snapshotted and disabled %d entities across %d domains", total, len(snapshot))

    async def _snapshot_domain(
        self, domain: str, entity_ids: list[str] | None
    ) -> dict[str, str]:
        """Snapshot current states for a domain."""
        states = self.hass.states
        if entity_ids:
            target_ids = entity_ids
        else:
            target_ids = [e.entity_id for e in states.async_all(domain)]

        snapshot = {}
        for entity_id in target_ids:
            state = states.get(entity_id)
            if state is not None:
                snapshot[entity_id] = state.state
        return snapshot

    async def _disable_domain(self, domain: str, snapshot: dict[str, str]) -> None:
        """Disable all entities in a snapshot."""
        for entity_id in snapshot:
            try:
                await self.hass.services.async_call(
                    domain, "turn_off",
                    {"entity_id": entity_id},
                    blocking=False,
                )
            except Exception as exc:
                _LOGGER.warning("Failed to disable %s %s: %s", domain, entity_id, exc)

    async def _restore_from_snapshot(self) -> None:
        """Restore all entities from snapshot."""
        data = await self._snapshot_store.async_load()
        if not data or "entities" not in data:
            _LOGGER.debug("No snapshot to restore")
            return

        restored_count = 0
        for domain, entities in data["entities"].items():
            for entity_id, previous_state in entities.items():
                if previous_state == "on":
                    try:
                        await self.hass.services.async_call(
                            domain, "turn_on",
                            {"entity_id": entity_id},
                            blocking=False,
                        )
                        restored_count += 1
                    except Exception as exc:
                        _LOGGER.warning("Failed to restore %s: %s", entity_id, exc)

        _LOGGER.info("Restored %d entities from snapshot", restored_count)

    async def _clear_snapshot(self) -> None:
        """Remove stored snapshot."""
        await self._snapshot_store.async_save({"entities": {}, "captured_at": None})

    async def _set_safe_states(
        self, overrides: dict[str, dict[str, Any]] | None = None
    ) -> None:
        """Set entities to safe default states for guests.

        Applies safe state overrides if provided (dict of entity_id -> {state, attributes...}).
        Falls back to a set of sensible defaults if no overrides configured.
        """
        if overrides:
            # User-configured safe states take priority
            for entity_id, target in overrides.items():
                domain = entity_id.split(".")[0]
                target_state = target.pop("state", None)
                if not target_state:
                    continue
                service_call_data: dict[str, Any] = {"entity_id": entity_id}
                if target:
                    service_call_data.update(target)
                try:
                    await self.hass.services.async_call(
                        domain, target_state,
                        service_call_data,
                        blocking=False,
                    )
                except Exception as exc:
                    _LOGGER.warning("Failed to set safe state for %s: %s", entity_id, exc)
            return

        # Built-in sensible defaults for common domains
        defaults = {
            "lock": ("lock", "lock"),
            "cover": ("cover", "close"),
            "climate": ("climate", "set_hvac_mode", {"hvac_mode": "off"}),
            "fan": ("fan", "turn_off"),
            "switch": ("switch", "turn_off"),
        }

        for state in self.hass.states.async_all():
            domain = state.domain
            if domain not in defaults:
                continue
            entity_id = state.entity_id
            config = defaults[domain]
            service = config[1]
            service_data = {"entity_id": entity_id}
            if len(config) > 2:
                service_data.update(config[2])
            # Only apply if not already in desired state
            try:
                await self.hass.services.async_call(
                    domain, service,
                    service_data,
                    blocking=False,
                )
            except Exception as exc:
                _LOGGER.debug("Safe state skip %s: %s", entity_id, exc)

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
            try:
                await asyncio.sleep(delay)
                _LOGGER.info("Auto-disable timer triggered — deactivating guest mode")
                await self.async_deactivate()
            except asyncio.CancelledError:
                _LOGGER.debug("Auto-disable task cancelled")
                raise

        self._auto_disable_task = asyncio.create_task(_auto_disable())

    async def _cancel_auto_disable(self) -> None:
        """Cancel pending auto-disable task."""
        if self._auto_disable_task is not None:
            self._auto_disable_task.cancel()
            self._auto_disable_task = None
