"""Tests for Gatekeeper HA — Auth Proxy.

These focus on the proxy's *logic*: CSRF/Origin enforcement, WiFi password
redaction, guest URL construction (uses the proxy port, not HA's), and the
fact that the token surface passed to scope checks contains scoped_* keys.
We do not start a real aiohttp server — the validation helpers are unit
tested directly via small fake request objects.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from custom_components.gatekeeper.auth_proxy import AuthProxyServer
from custom_components.gatekeeper.token_manager import TokenManager


class _FakeRequest:
    """Minimal stand-in for aiohttp.web.Request for CSRF/origin checks."""

    def __init__(self, headers=None, path="/api/test"):
        self.headers = headers or {}
        self.path = path


@pytest.fixture
def proxy(hass):
    tm = TokenManager(hass)
    entry = SimpleNamespace(entry_id="e1", options={})
    return AuthProxyServer(hass, tm, entry, port=58921, host="127.0.0.1")


def test_build_guest_url_uses_proxy_port(proxy):
    """Guest URL must point at the proxy's port, not the HA UI port."""
    proxy.external_url = "http://example.com:58921"
    url = proxy.build_guest_url("gk_abc", "secret")
    assert url == "http://example.com:58921/gatekeeper/guest/gk_abc/secret"
    # Falls back to bind host/port if external_url unset
    proxy.external_url = ""
    url = proxy.build_guest_url("gk_abc", "secret")
    assert url == "http://127.0.0.1:58921/gatekeeper/guest/gk_abc/secret"


def test_check_browser_origin_same_origin_allowed(proxy):
    req = _FakeRequest(headers={"Sec-Fetch-Site": "same-origin"})
    assert proxy._check_browser_origin(req) is True


def test_check_browser_origin_cross_site_rejected(proxy):
    req = _FakeRequest(headers={"Sec-Fetch-Site": "cross-site"})
    assert proxy._check_browser_origin(req) is False


def test_check_browser_origin_origin_host_match(proxy):
    req = _FakeRequest(headers={
        "Origin": "http://gk.example.com:58921",
        "Host": "gk.example.com:58921",
    })
    assert proxy._check_browser_origin(req) is True


def test_check_browser_origin_origin_host_mismatch_rejected(proxy):
    req = _FakeRequest(headers={
        "Origin": "http://evil.example.com",
        "Host": "gk.example.com:58921",
    })
    assert proxy._check_browser_origin(req) is False


def test_check_browser_origin_no_fetch_no_origin_allowed(proxy):
    """Curl/scripted clients without Origin/Sec-Fetch headers are allowed.

    The bearer secret is in the URL; the CSRF risk we are mitigating is a
    third-party page in the guest's browser, which always sends these
    headers.
    """
    req = _FakeRequest(headers={})
    assert proxy._check_browser_origin(req) is True


def test_is_service_allowed_with_full_token(proxy):
    """Scope check must see scoped_entities/domains from the safe-token surface."""
    token = {
        "token_id": "gk_x",
        "is_active": True,
        "scoped_entities": ["light.kitchen"],
        "scoped_domains": ["light"],
        "allowed_services": [],
    }
    assert proxy._is_service_allowed(token, "light", "turn_on", "light.kitchen") is True
    assert proxy._is_service_allowed(token, "light", "turn_on", "light.bedroom") is False
    assert proxy._is_service_allowed(token, "switch", "turn_on", "switch.foo") is False


@pytest.mark.asyncio
async def test_handle_status_redacts_wifi_password_by_default(hass):
    """The status endpoint must not leak the WiFi password without explicit opt-in."""
    tm = TokenManager(hass)
    await tm.async_load()
    entry = SimpleNamespace(
        entry_id="e1",
        options={"wifi_ssid": "HomeNet", "wifi_password": "supersecret"},
    )
    proxy = AuthProxyServer(hass, tm, entry, port=58921, host="127.0.0.1")

    token = await tm.async_create_token(
        label="t", duration_hours=24, show_wifi=False,
    )

    # Call the validator+handler logic directly. We don't spin up aiohttp;
    # we craft a request object matching the handler's expectations.
    class _Req:
        def __init__(self, tid, sec):
            self.match_info = {"token_id": tid, "token_secret": sec}
            self.headers = {}

    resp = await proxy._handle_status(_Req(token["token_id"], token["_secret"]))
    body = _read_json_response(resp)
    assert body["wifi_ssid"] == "HomeNet"
    assert body["wifi_password"] == ""  # redacted
    assert body["wifi_password_available"] is False


@pytest.mark.asyncio
async def test_handle_status_exposes_password_with_full_opt_in(hass):
    """Requires both per-token AND global show_wifi to expose the password."""
    tm = TokenManager(hass)
    await tm.async_load()
    entry = SimpleNamespace(
        entry_id="e1",
        options={
            "wifi_ssid": "HomeNet",
            "wifi_password": "supersecret",
            "show_wifi": True,
        },
    )
    proxy = AuthProxyServer(hass, tm, entry, port=58921, host="127.0.0.1")

    token = await tm.async_create_token(
        label="t", duration_hours=24, show_wifi=True,
    )

    class _Req:
        def __init__(self, tid, sec):
            self.match_info = {"token_id": tid, "token_secret": sec}
            self.headers = {}

    resp = await proxy._handle_status(_Req(token["token_id"], token["_secret"]))
    body = _read_json_response(resp)
    assert body["wifi_password"] == "supersecret"
    assert body["wifi_password_available"] is True


@pytest.mark.asyncio
async def test_handle_call_service_rejects_cross_site(hass):
    """Cross-site requests must be rejected before any service call happens."""
    tm = TokenManager(hass)
    await tm.async_load()
    entry = SimpleNamespace(entry_id="e1", options={})
    proxy = AuthProxyServer(hass, tm, entry, port=58921, host="127.0.0.1")

    token = await tm.async_create_token(label="t", duration_hours=24)

    class _Req:
        path = "/api/test"

        def __init__(self):
            self.match_info = {
                "token_id": token["token_id"],
                "token_secret": token["_secret"],
            }
            self.headers = {
                "Sec-Fetch-Site": "cross-site",
                "Content-Type": "application/json",
            }

        async def json(self):
            return {}

    resp = await proxy._handle_call_service(_Req())
    assert resp.status == 403


@pytest.mark.asyncio
async def test_handle_call_service_rejects_non_json_content_type(hass):
    """Form-encoded posts (the classic CSRF vector) are rejected with 415."""
    tm = TokenManager(hass)
    await tm.async_load()
    entry = SimpleNamespace(entry_id="e1", options={})
    proxy = AuthProxyServer(hass, tm, entry, port=58921, host="127.0.0.1")

    token = await tm.async_create_token(label="t", duration_hours=24)

    class _Req:
        def __init__(self):
            self.match_info = {
                "token_id": token["token_id"],
                "token_secret": token["_secret"],
            }
            self.headers = {
                "Sec-Fetch-Site": "same-origin",
                "Content-Type": "application/x-www-form-urlencoded",
            }

        async def json(self):
            return {}

    resp = await proxy._handle_call_service(_Req())
    assert resp.status == 415


def _read_json_response(resp):
    """Extract the JSON body from an aiohttp Response object."""
    import json
    return json.loads(resp.body.decode("utf-8"))
