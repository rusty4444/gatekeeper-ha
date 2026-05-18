# Gatekeeper HA

**QR-code-based temporary guest access for Home Assistant.**

A native custom integration + Lovelace card that lets you generate time-limited, scoped guest tokens and serve them via a standalone guest page — no app install required.

## Features

- **🔑 Scoped guest tokens** — generate time-limited URLs that grant access only to specific entities, domains, and services
- **📱 Standalone guest page** — guests just scan a QR code or open a link. No HA login, no app install
- **⏱️ Auto-expiry** — tokens expire after a configured duration. Use limits also supported
- **🛡️ Guest mode** — toggle a full guest mode that disables selected automations and revokes all tokens on exit
- **📋 Admin Lovelace card** — create/revoke tokens, see remaining time, display QR code, toggle guest mode — all from a card on your dashboard
- **🧩 Automation blueprints** — shipped with doorbell → auto-token, token expiry alert, and lock-code → guest mode blueprints
- **⚙️ Fully UI-configurable** — set up via Settings → Devices & Services, no YAML editing

## Quick Start

### 1. Install via HACS

Gatekeeper HA is not yet in the default HACS store. For now:

1. Add as a **Custom Repository** in HACS:
   - URL: `https://github.com/rusty4444/gatekeeper-ha`
   - Category: Integration
2. Download the integration
3. Restart Home Assistant

### 2. Install the Lovelace Card

1. Go to HACS → Frontend → Custom Repositories
2. Add: `https://github.com/rusty4444/gatekeeper-ha`
3. Category: Lovelace
4. Find **Gatekeeper Guest Portal** and install
5. Add the resource: `/hacsfiles/gatekeeper-card/gatekeeper-card.js`
6. Add card to any dashboard: `type: custom:gatekeeper-card`

### 3. Configure

1. Go to **Settings → Devices & Services → Add Integration**
2. Search for "Gatekeeper HA"
3. Configure the guest page port (default: 8921) and default token expiry
4. The card will appear in your Lovelace card picker

### 4. Share access

1. From the Gatekeeper card, tap **+ New Token**
2. Set a label (e.g. "Plumber Wednesday"), scope (e.g. `lock.*`, `light.*`), and duration
3. The card shows a QR code — screenshot it, or copy the guest URL
4. Guest opens the link and gets a simple page with the controls you allowed

## Configuration

All configuration is via the UI. Go to **Settings → Devices & Services → Gatekeeper HA → Configure**.

| Option | Default | Description |
|--------|---------|-------------|
| Guest page port | 8921 | Port for the standalone guest web page |
| Default token expiry | 24h | Default hours for new guest tokens |
| Auto-disable after | 48h | Auto-disable guest mode after N hours (0 = manual) |

## Blueprints

Three automation blueprints are bundled in `/blueprints/`:

| Blueprint | What it does |
|-----------|-------------|
| `guest_arrived.yaml` | Someone rings the doorbell → auto-creates a 4-hour token, sends it to your phone |
| `token_expiry_alert.yaml` | Every 15 minutes checks if any token is near expiry → sends alert |
| `guest_mode_lock.yaml` | Guest enters a specific lock code → activates guest mode with auto-disable |

## Architecture

```
Custom integration (custom_components/gatekeeper/)
├── token_manager.py      # Token CRUD, bcrypt hashing, expiry engine
├── guest_mode.py         # State machine, automation snapshot/restore
├── auth_proxy.py         # Standalone asyncio HTTP server (guest page + proxy)
├── config_flow.py        # Full UI-based setup
├── services.yaml         # 6 HA services (create/revoke token, activate/deactivate mode, etc.)
└── ...

Lovelace card (gatekeeper-card/)
├── src/index.js          # LitElement card — admin panel, QR display, token management
└── ...

Blueprints (blueprints/)
├── guest_arrived.yaml
├── token_expiry_alert.yaml
└── guest_mode_lock.yaml
```

## Security

- Guest tokens never expose the raw secret in logs (hashed with bcrypt)
- The guest page runs on a separate port (configurable, defaults to 8921)
- All scope enforcement happens server-side — the guest's JS never overrides permissions
- Token IDs are generated with `secrets.token_urlsafe(32)`
- Tokens can be use-limited (N API calls) in addition to time-limited
- Guest mode snapshots automations on activate and restores them on deactivate

## Development

```bash
# Clone
git clone https://github.com/rusty4444/gatekeeper-ha
cd gatekeeper-ha

# Install test deps
pip install -r requirements-dev.txt

# Run tests
pytest tests/

# Build Lovelace card
cd gatekeeper-card && npm install && npm run build
```

## Requirements

- Home Assistant 2025.8.0+
- Python 3.12+

## License

MIT
