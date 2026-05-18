"""Pytest configuration for Gatekeeper HA tests.

These tests rely on `pytest-homeassistant-custom-component`, which provides a
real `hass` fixture (running on an asyncio loop) along with `hass_storage` and
`MockConfigEntry`. The previous hand-rolled MagicMock-based `hass` fixture
could not satisfy HA's `Store.async_load` (which awaits
`hass.async_add_executor_job`) and made every storage-touching test crash with
``TypeError: object MagicMock can't be used in 'await' expression``.

Anything project-specific can be added here; the HA fixtures themselves come
from the plugin and do not need to be re-declared.
"""

from __future__ import annotations

# Enables the HA fixtures (`hass`, `hass_storage`, `MockConfigEntry`, ...).
pytest_plugins = ["pytest_homeassistant_custom_component"]


def pytest_configure(config):  # noqa: D401 - pytest hook signature
    """Auto-enable custom-component loading for every test."""
    # Required by pytest-homeassistant-custom-component so HA permits
    # importing from `custom_components/`.
    config.addinivalue_line(
        "markers",
        "enable_custom_integrations: enable loading of custom_components in HA fixture",
    )


# Apply the enable_custom_integrations fixture globally.
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Automatically allow custom integrations in every test."""
    yield
