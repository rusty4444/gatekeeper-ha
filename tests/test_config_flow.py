"""Tests for Gatekeeper HA config flow helpers."""

from __future__ import annotations

import pytest
import voluptuous as vol

from custom_components.gatekeeper.config_flow import _normalize_public_guest_base_url


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("", ""),
        ("   ", ""),
        ("https://garage.example.com", "https://garage.example.com"),
        ("https://garage.example.com/", "https://garage.example.com"),
        (
            " http://garage.example.com:8921/path/ ",
            "http://garage.example.com:8921/path",
        ),
    ],
)
def test_normalize_public_guest_base_url_accepts_empty_and_http_urls(value, expected):
    assert _normalize_public_guest_base_url(value) == expected


@pytest.mark.parametrize(
    "value",
    [
        "garage.example.com",
        "ftp://garage.example.com",
        "https://",
        "https://garage.example.com?token=abc",
        "https://garage.example.com#guest",
        "https://garage example.com",
    ],
)
def test_normalize_public_guest_base_url_rejects_invalid_urls(value):
    with pytest.raises(vol.Invalid):
        _normalize_public_guest_base_url(value)
