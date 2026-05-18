"""Pytest configuration for Gatekeeper HA tests."""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock

import pytest


@pytest.fixture
def hass():
    """Create a mock Home Assistant instance for testing."""
    hass = MagicMock()
    hass.data = {}
    hass.states = MagicMock()
    hass.states.async_all = MagicMock(return_value=[])
    hass.states.get = MagicMock(return_value=None)

    # Mock services
    hass.services = MagicMock()
    hass.services.async_call = MagicMock()

    # Mock bus
    hass.bus = MagicMock()
    hass.bus.async_fire = MagicMock()

    return hass


@pytest.fixture
def hass_with_states(hass):
    """Create a mock HA instance with some entities."""
    from types import SimpleNamespace

    light_living = SimpleNamespace(
        entity_id="light.living_room",
        domain="light",
        state="on",
        attributes={"friendly_name": "Living Room Light"},
    )
    light_kitchen = SimpleNamespace(
        entity_id="light.kitchen",
        domain="light",
        state="off",
        attributes={"friendly_name": "Kitchen Light"},
    )
    lock_door = SimpleNamespace(
        entity_id="lock.front_door",
        domain="lock",
        state="locked",
        attributes={"friendly_name": "Front Door"},
    )
    climate_upstairs = SimpleNamespace(
        entity_id="climate.upstairs",
        domain="climate",
        state="cool",
        attributes={"friendly_name": "Upstairs Thermostat", "temperature": 22},
    )
    sensor_temp = SimpleNamespace(
        entity_id="sensor.temperature",
        domain="sensor",
        state="21.5",
        attributes={"friendly_name": "Temperature"},
    )

    hass.states.async_all = MagicMock(
        return_value=[light_living, light_kitchen, lock_door, climate_upstairs, sensor_temp]
    )

    return hass
