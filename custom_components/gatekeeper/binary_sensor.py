"""Binary sensor entities for Gatekeeper HA."""

from __future__ import annotations

import logging

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
)

from .const import *
from .sensor import GatekeeperCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gatekeeper binary sensor entities."""
    coordinator = hass.data.get(DOMAIN, {}).get("coordinator")
    if not coordinator:
        _LOGGER.warning("Coordinator not found for binary sensor setup")
        return

    async_add_entities([
        GuestModeActiveBinarySensor(coordinator, entry),
    ])


class GuestModeActiveBinarySensor(CoordinatorEntity, BinarySensorEntity):
    """Binary sensor indicating whether guest mode is currently active."""

    _attr_name = "Guest mode active"
    _attr_unique_id = BINARY_SENSOR_MODE
    _attr_icon = "mdi:shield-account"
    _attr_device_class = BinarySensorDeviceClass.SAFETY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

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
    def is_on(self) -> bool:
        """Return True if guest mode is active."""
        return self.coordinator.data.get("mode_active", False)
