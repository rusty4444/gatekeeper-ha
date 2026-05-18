"""Auth proxy server for Gatekeeper HA — standalone HTTP server serving the guest page."""

from __future__ import annotations

import asyncio
import logging
from typing import Any
from datetime import datetime, timezone

from homeassistant.core import HomeAssistant

from .const import *
from .token_manager import TokenManager

_LOGGER = logging.getLogger(__name__)

GUEST_PAGE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Guest — Gatekeeper</title>
<style>
  :root { --bg: #121212; --card: #1e1e1e; --text: #eee; --accent: #6c5ce7; }
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         background: var(--bg); color: var(--text); min-height: 100vh; }
  .container { max-width: 480px; margin: 0 auto; padding: 16px; }
  .header { text-align: center; padding: 24px 0 16px; }
  .header h1 { font-size: 1.4rem; font-weight: 600; }
  .timer-bar { background: var(--card); border-radius: 12px; padding: 12px 16px;
               margin-bottom: 16px; display: flex; justify-content: space-between; }
  .timer-bar .label { opacity: 0.7; font-size: 0.85rem; }
  .timer-bar .time { font-weight: 600; color: var(--accent); }
  .entity-card { background: var(--card); border-radius: 12px; padding: 16px;
                 margin-bottom: 12px; display: flex; justify-content: space-between;
                 align-items: center; }
  .entity-card .name { font-weight: 500; }
  .entity-card .state { font-size: 0.85rem; opacity: 0.7; }
  .entity-card .controls { display: flex; gap: 8px; }
  .btn { padding: 8px 16px; border: none; border-radius: 8px; font-size: 0.85rem;
         font-weight: 500; cursor: pointer; transition: all 0.2s; }
  .btn-on { background: var(--accent); color: #fff; }
  .btn-off { background: #333; color: #aaa; }
  .btn:active { transform: scale(0.95); }
  .wifi-info { background: var(--card); border-radius: 12px; padding: 16px; margin-top: 16px; }
  .wifi-info h3 { font-size: 0.9rem; opacity: 0.7; margin-bottom: 8px; }
  .wifi-info .detail { display: flex; justify-content: space-between; padding: 4px 0; }
  .error { color: #ff6b6b; text-align: center; padding: 16px; }
  .loading { text-align: center; padding: 48px; opacity: 0.5; }
</style>
</head>
<body>
<div class="container" id="app">
  <div class="loading">Loading guest controls...</div>
</div>
<script>
(function() {
  const pathParts = window.location.pathname.split('/');
  const tokenId = pathParts[3];
  const tokenSecret = pathParts[4];
  const BASE = '/api/gatekeeper/guest/' + tokenId + '/' + tokenSecret;

  async function callService(domain, service, entityId, data) {
    const resp = await fetch(BASE + '/call_service', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ domain, service, entity_id: entityId, data: data || {} })
    });
    return resp.json();
  }

  async function fetchEntities() {
    const resp = await fetch(BASE + '/entities');
    return resp.json();
  }

  async function fetchStatus() {
    const resp = await fetch(BASE + '/status');
    return resp.json();
  }

  async function render() {
    const app = document.getElementById('app');
    try {
      const status = await fetchStatus();
      const entities = await fetchEntities();

      let html = '<div class="header"><h1>Guest Controls</h1></div>';
      html += '<div class="timer-bar"><span class="label">Session expires</span><span class="time" id="timer">' +
              (status.expires_in || '--') + '</span></div>';

      html += '<div id="entities">';
      entities.forEach(e => {
        html += '<div class="entity-card">';
        html += '<div><div class="name">' + (e.friendly_name || e.entity_id) + '</div>';
        html += '<div class="state">' + (e.state || 'unknown') + '</div></div>';
        html += '<div class="controls">';
        html += '<button class="btn btn-on" onclick="toggleEntity(\'' + e.entity_id + '\', \'on\')">On</button>';
        html += '<button class="btn btn-off" onclick="toggleEntity(\'' + e.entity_id + '\', \'off\')">Off</button>';
        if (e.domain === 'lock') {
          html += '<button class="btn btn-on" onclick="toggleEntity(\'' + e.entity_id + '\', \'unlock\')">Unlock</button>';
        }
        html += '</div></div>';
      });
      html += '</div>';

      html += '<div class="wifi-info"><h3>WiFi &amp; House Info</h3>';
      html += '<div class="detail"><span>Network</span><span>' + (status.wifi_ssid || '--') + '</span></div>';
      html += '<div class="detail"><span>Password</span><span>' + (status.wifi_password || '--') + '</span></div>';
      html += '</div>';

      app.innerHTML = html;

      if (status.expires_at) {
        const expires = new Date(status.expires_at + 'Z').getTime();
        setInterval(function() {
          const now = new Date().getTime();
          const diff = Math.max(0, expires - now);
          const h = Math.floor(diff / 3600000);
          const m = Math.floor((diff % 3600000) / 60000);
          document.getElementById('timer').textContent = h + 'h ' + m + 'm';
        }, 10000);
      }
    } catch(e) {
      app.innerHTML = '<div class="error">Failed to load guest controls. Invalid or expired link.</div>';
    }
  }

  window.toggleEntity = async function(entityId, action) {
    const domain = entityId.split('.')[0];
    let service = action;
    if (action === 'on') service = 'turn_on';
    else if (action === 'off') service = 'turn_off';
    else if (action === 'unlock') service = 'unlock';
    await callService(domain, service, entityId);
    render();
  };

  render();
})();
</script>
</body>
</html>"""


class AuthProxyServer:
    """Lightweight asyncio HTTP server that serves the guest page and proxies scoped API calls."""

    def __init__(
        self,
        hass: HomeAssistant,
        token_manager: TokenManager,
        port: int = DEFAULT_GUEST_PAGE_PORT,
        host: str = "127.0.0.1",
    ) -> None:
        self.hass = hass
        self._token_manager = token_manager
        self._port = port
        self._host = host
        self._runner: Any = None
        self._server: asyncio.AbstractServer | None = None
        self.external_url: str = ""

    async def async_start(self) -> None:
        """Start the HTTP server."""
        from aiohttp import web

        app = web.Application()
        app.router.add_get("/gatekeeper/guest/{token_id}/{token_secret}", self._handle_guest_page)
        app.router.add_get("/api/gatekeeper/guest/{token_id}/{token_secret}/entities", self._handle_entities)
        app.router.add_get("/api/gatekeeper/guest/{token_id}/{token_secret}/status", self._handle_status)
        app.router.add_post("/api/gatekeeper/guest/{token_id}/{token_secret}/call_service", self._handle_call_service)

        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, self._host, self._port)
        self._server = await site.start()

        # Build external URL template (token_id/secret filled in by caller)
        ha_url = self.hass.config.external_url or f"http://{self._host}:{self._port}"
        self.external_url = f"{ha_url}/gatekeeper/guest/TOKEN_ID/TOKEN_SECRET"

        _LOGGER.info("Gatekeeper guest proxy started on %s:%d", self._host, self._port)

    async def async_stop(self, *args) -> None:
        """Stop the HTTP server and clean up the aiohttp app runner."""
        if self._server:
            self._server.close()
            await self._server.wait_closed()
            self._server = None
        if self._runner:
            await self._runner.cleanup()
            self._runner = None
        _LOGGER.info("Gatekeeper guest proxy stopped")

    async def _validate_request(self, request) -> dict[str, Any] | None:
        """Validate token from URL path. Returns token dict or None."""
        token_id = request.match_info.get("token_id")
        token_secret = request.match_info.get("token_secret")
        if not token_id or not token_secret:
            return None
        return await self._token_manager.async_validate_token(token_id, token_secret)

    async def _handle_guest_page(self, request) -> "web.Response":
        """Serve the standalone guest page."""
        from aiohttp import web

        token = await self._validate_request(request)
        if token is None:
            return web.Response(
                text="<html><body><h1>Invalid or expired link</h1><p>Please ask the homeowner for a new guest link.</p></body></html>",
                content_type="text/html",
                status=401,
            )

        return web.Response(text=GUEST_PAGE_HTML, content_type="text/html")

    async def _handle_entities(self, request) -> "web.Response":
        """Return scoped entity states for this token."""
        from aiohttp import web

        token = await self._validate_request(request)
        if token is None:
            return web.json_response({"error": "Invalid token"}, status=401)

        entities = self._get_scoped_entities(token)
        return web.json_response(entities)

    async def _handle_status(self, request) -> "web.Response":
        """Return token status including expiry timer."""
        from aiohttp import web

        token = await self._validate_request(request)
        if token is None:
            return web.json_response({"error": "Invalid token"}, status=401)

        # Safely read config entry options
        entry = self.hass.config_entries.async_get_entry(DOMAIN)
        wifi_ssid = entry.options.get("wifi_ssid", "") if entry else ""
        wifi_password = entry.options.get("wifi_password", "") if entry else ""

        return web.json_response({
            "active": True,
            "expires_at": token.get("expires_at"),
            "expires_in": self._format_remaining(token.get("expires_at")),
            "wifi_ssid": wifi_ssid,
            "wifi_password": wifi_password,
        })

    async def _handle_call_service(self, request) -> "web.Response":
        """Proxy a service call with scope validation."""
        from aiohttp import web

        token = await self._validate_request(request)
        if token is None:
            return web.json_response({"error": "Invalid token"}, status=401)

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        domain = body.get("domain", "")
        service = body.get("service", "")
        entity_id = body.get("entity_id", "")
        service_data = body.get("data", {})

        # Scope validation
        if not self._is_service_allowed(token, domain, service, entity_id):
            return web.json_response({"error": "Service not in scope"}, status=403)

        try:
            await self.hass.services.async_call(
                domain, service,
                {"entity_id": entity_id, **service_data},
                blocking=False,
            )
            return web.json_response({"success": True})
        except Exception as exc:
            _LOGGER.warning("Guest service call failed: %s", exc)
            return web.json_response({"error": str(exc)}, status=500)

    def _get_scoped_entities(self, token: dict[str, Any]) -> list[dict[str, Any]]:
        """Return entity states matching the token's scope."""
        scoped_domains = set(token.get("scoped_domains", []))
        scoped_entities = token.get("scoped_entities", [])

        results = []
        for state in self.hass.states.async_all():
            domain = state.domain
            entity_id = state.entity_id

            # Check domain scope
            if scoped_domains and domain not in scoped_domains:
                continue

            # Check entity glob scope
            if scoped_entities:
                in_scope = False
                for pattern in scoped_entities:
                    if entity_id.startswith(pattern.replace("*", "").rstrip(".")):
                        in_scope = True
                        break
                if not in_scope:
                    continue

            results.append({
                "entity_id": entity_id,
                "domain": domain,
                "state": state.state,
                "friendly_name": state.attributes.get("friendly_name", ""),
            })

        return results

    def _is_service_allowed(
        self, token: dict[str, Any], domain: str, service: str, entity_id: str
    ) -> bool:
        """Check if a service call is within the token's scope."""
        # Check allowed services
        allowed_services = token.get("allowed_services", [])
        if allowed_services:
            service_key = f"{domain}.{service}"
            if service_key not in allowed_services:
                _LOGGER.warning("Guest tried %s — not in allowed services", service_key)
                return False

        # Check entity scope
        scoped_entities = token.get("scoped_entities", [])
        if scoped_entities:
            in_scope = False
            for pattern in scoped_entities:
                if entity_id.startswith(pattern.replace("*", "").rstrip(".")):
                    in_scope = True
                    break
            if not in_scope:
                _LOGGER.warning("Guest tried %s — entity not in scope", entity_id)
                return False

        # Check domain scope
        scoped_domains = set(token.get("scoped_domains", []))
        if scoped_domains and domain not in scoped_domains:
            _LOGGER.warning("Guest tried %s — domain not in scope", domain)
            return False

        return True

    @staticmethod
    def _format_remaining(expires_at: str | None) -> str:
        """Format remaining time as human-readable string."""
        if not expires_at:
            return "--"
        try:
            expires = datetime.fromisoformat(expires_at)
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            if remaining <= 0:
                return "Expired"
            hours = int(remaining // 3600)
            minutes = int((remaining % 3600) // 60)
            return f"{hours}h {minutes}m"
        except (ValueError, TypeError):
            return "--"
