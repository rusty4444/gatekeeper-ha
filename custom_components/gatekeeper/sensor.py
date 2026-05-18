"""Sensor entities for Gatekeeper HA."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import *

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gatekeeper sensor entities."""
    coordinator = GatekeeperCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()

    async_add_entities([
        GatekeeperActiveTokensSensor(coordinator, entry),
        GatekeeperSoonestExpirySensor(coordinator, entry),
    ])


class GatekeeperCoordinator(DataUpdateCoordinator):
    """Coordinator that polls token and guest mode state for sensors."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name="Gatekeeper",
            update_interval=COORDINATOR_UPDATE_INTERVAL,
        )
        self.entry = entry

    async def _async_update_data(self) -> dict:
        """Fetch current state from managers."""
        token_manager = self.hass.data.get(DOMAIN, {}).get("token_manager")
        guest_mode = self.hass.data.get(DOMAIN, {}).get("guest_mode")

        tokens = []
        soonest_expiry = None
        if token_manager:
            tokens = await token_manager.async_list_active()
            valid_expiries = [
                t["expires_at"] for t in tokens
                if t.get("expires_at")
            ]
            if valid_expiries:
                soonest_expiry = min(valid_expiries)

        mode_active = False
        mode_remaining = None
        if guest_mode:
            mode_active = guest_mode.is_active
            mode_remaining = guest_mode.remaining_seconds

        return {
            "tokens": tokens,
            "token_count": len(tokens),
            "soonest_expiry": soonest_expiry,
            "mode_active": mode_active,
            "mode_remaining": mode_remaining,
        }


class GatekeeperActiveTokensSensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the number of active guest tokens."""

    _attr_name = "Gatekeeper active tokens"
    _attr_unique_id = SENSOR_TOKENS
    _attr_icon = "mdi:ticket-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = "tokens"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: GatekeeperCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Gatekeeper HA",
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def native_value(self) -> int:
        """Return current token count."""
        return self.coordinator.data.get("token_count", 0)

    @property
    def extra_state_attributes(self) -> dict:
        """Return token list as attributes."""
        return {
            "tokens": self.coordinator.data.get("tokens", []),
        }


class GatekeeperSoonestExpirySensor(CoordinatorEntity, SensorEntity):
    """Sensor showing the nearest token expiry timestamp."""

    _attr_name = "Gatekeeper soonest expiry"
    _attr_unique_id = SENSOR_SOONEST_EXPIRY
    _attr_icon = "mdi:timer-outline"
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(
        self, coordinator: GatekeeperCoordinator, entry: ConfigEntry
    ) -> None:
        super().__init__(coordinator)
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Gatekeeper HA",
            "manufacturer": MANUFACTURER,
            "entry_type": "service",
        }

    @property
    def native_value(self) -> datetime | None:
        """Return the soonest expiry as a datetime."""
        soonest = self.coordinator.data.get("soonest_expiry")
        if soonest:
            try:
                return datetime.fromisoformat(soonest)
            except (ValueError, TypeError):
                return None
        return None
