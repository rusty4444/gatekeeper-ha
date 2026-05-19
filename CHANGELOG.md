# Changelog

## [0.1.3] — 2026-05-19

### Fixed
- Config flow 500 error on HA 2026.4+ (Python 3.14) — relaxed `bcrypt==4.2.1` to `bcrypt>=4.2.1,<6.0.0`

## [0.1.2] — 2026-05-19

### Security
- CSRF protection on `/call_service` endpoint (cross-site, host mismatch, Content-Type enforcement)
- WiFi password redacted in `/status` unless both per-token and global options enable it
- Guest secret on card changed to password field with reveal/hide, dismiss, and 60s auto-clear
- TOCTOU fix: token validate + use-count increment now atomic under a single lock

### Fixed
- Guest URL now uses proxy bind host+port instead of HA UI port (8123)
- `GuestModeManager` properly cancels auto-disable timer on shutdown
- State keyed by `entry.entry_id` for correct multi-entry teardown
- `async_revoke_all` accepts `source` filter so guest mode doesn't revoke admin tokens
- Safe-state overrides map values (`on`, `off`, `locked`) to real service names (`turn_on`, `turn_off`, `lock`)
- Safe-state no-op path skips service calls entirely when no overrides exist
- Sensor/binary_sensor coordinator-missing path now logs at `ERROR` level
- Dead SHA-256 fallback removed; bcrypt is a hard requirement
- Explicit imports throughout (no more `from .const import *`)

### Changed
- Lovelace card split into dedicated repo: [rusty4444/gatekeeper-card](https://github.com/rusty4444/gatekeeper-card)
- `async_create_token` returns full safe-token surface (no hash exposure)
- `_safe_token` only strips `token_hash` — proxy sees scoped fields for enforcement

### Added
- Tests for auth proxy, safe-state, and guest mode (33 passing)

## [0.1.0] — 2026-05-18

Initial release.
