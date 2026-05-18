/**
 * Gatekeeper HA — Lovelace Card
 * Admin panel for managing guest tokens and guest mode.
 *
 * Installation:
 * 1. Add as custom repository in HACS (type: Lovelace)
 * 2. Add resource: /hacsfiles/gatekeeper-card/gatekeeper-card.js
 * 3. Add card: type: custom:gatekeeper-card
 *
 * Configuration:
 *   type: custom:gatekeeper-card
 *   title: "Guest Access"
 *   show_qr: true
 *   default_duration: 24
 */

// Lit is imported from npm and bundled by rollup (see rollup.config.js).
// Do NOT switch this to a CDN URL — HA frontends should not require
// internet access at render time, and unpkg in particular has been
// observed to serve stale/redirected modules.
import { LitElement, html, css } from 'lit';

class GatekeeperCard extends LitElement {
  static get properties() {
    return {
      _hass: { type: Object },
      _config: { type: Object },
      _tokens: { type: Array },
      _modeActive: { type: Boolean },
      _modeRemaining: { type: String },
      _guestUrl: { type: String },
      _loading: { type: Boolean },
      _newToken: { type: Object },
      _showCreateForm: { type: Boolean },
      _error: { type: String },
    };
  }

  constructor() {
    super();
    this._tokens = [];
    this._modeActive = false;
    this._modeRemaining = '';
    this._guestUrl = '';
    this._loading = true;
    this._newToken = null;
    this._showCreateForm = false;
    this._error = '';
  }

  set hass(hass) {
    this._hass = hass;
    this._refresh();
  }

  setConfig(config) {
    this._config = {
      title: 'Guest Access',
      show_qr: true,
      default_duration: 24,
      ...config,
    };
  }

  async _refresh() {
    if (!this._hass) return;
    this._loading = true;

    try {
      const [tokensResult, modeState, urlResult] = await Promise.all([
        this._hass.callService('gatekeeper', 'get_tokens', {}, { return_response: true }),
        this._getModeState(),
        this._hass.callService('gatekeeper', 'get_guest_url', {}, { return_response: true }),
      ]);

      this._tokens = tokensResult?.response?.tokens || [];

      if (urlResult?.response?.url) {
        this._guestUrl = urlResult.response.url;
      }

      this._modeActive = modeState;
      this._error = '';
    } catch (e) {
      this._error = 'Failed to load Gatekeeper data: ' + e.message;
    }

    this._loading = false;
  }

  async _getModeState() {
    try {
      const state = this._hass.states['binary_sensor.guest_mode_active'];
      // Populate the remaining-time string so the header reflects auto-disable countdown.
      const remaining = state?.attributes?.mode_remaining_seconds;
      if (typeof remaining === 'number' && remaining > 0) {
        const h = Math.floor(remaining / 3600);
        const m = Math.floor((remaining % 3600) / 60);
        this._modeRemaining = h > 0 ? `${h}h ${m}m` : `${m}m`;
      } else {
        this._modeRemaining = '';
      }
      return state?.state === 'on';
    } catch {
      this._modeRemaining = '';
      return false;
    }
  }

  async _createToken(e) {
    e.preventDefault();
    const form = e.target;
    const data = new FormData(form);

    this._loading = true;
    this._newToken = null;
    this._error = '';

    try {
      const result = await this._hass.callService('gatekeeper', 'create_token', {
        label: data.get('label') || 'Guest',
        duration: parseInt(data.get('duration')) || this._config.default_duration,
        scoped_entities: (data.get('entities') || 'light.*').split(',').map(s => s.trim()),
        scoped_domains: (data.get('domains') || 'light,switch,climate').split(',').map(s => s.trim()),
        allowed_services: data.get('services') ? data.get('services').split(',').map(s => s.trim()) : null,
      }, { return_response: true });

      if (result?.response) {
        this._newToken = result.response;
      }

      this._showCreateForm = false;
      await this._refresh();
    } catch (e) {
      this._error = 'Failed to create token: ' + e.message;
    }

    this._loading = false;
  }

  async _revokeToken(tokenId) {
    this._loading = true;
    try {
      await this._hass.callService('gatekeeper', 'revoke_token', { token_id: tokenId });
      await this._refresh();
    } catch (e) {
      this._error = 'Failed to revoke token: ' + e.message;
    }
    this._loading = false;
  }

  async _toggleMode() {
    this._loading = true;
    try {
      if (this._modeActive) {
        await this._hass.callService('gatekeeper', 'deactivate_mode', {});
      } else {
        await this._hass.callService('gatekeeper', 'activate_mode', {
          auto_disable_after: 48,
          disable_automations: true,
        });
      }
      await this._refresh();
    } catch (e) {
      this._error = 'Failed to toggle guest mode: ' + e.message;
    }
    this._loading = false;
  }

  _copyToClipboard(text) {
    navigator.clipboard.writeText(text).catch(() => {});
  }

  _formatExpiry(iso) {
    if (!iso) return '--';
    // Tolerate both 'Z' and '+00:00' suffixes that the server may emit.
    const stamp = /Z$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : iso + 'Z';
    const expires = new Date(stamp);
    const now = new Date();
    const diff = Math.max(0, expires - now);
    const h = Math.floor(diff / 3600000);
    const m = Math.floor((diff % 3600000) / 60000);
    if (h > 48) return `${Math.floor(h / 24)}d ${h % 24}h`;
    return `${h}h ${m}m`;
  }

  _getStatusClass(token) {
    if (!token.is_active) return 'status-revoked';
    const expires = new Date(token.expires_at + 'Z');
    const now = new Date();
    const diff = expires - now;
    if (diff < 3600000) return 'status-expiring'; // < 1h
    if (diff < 86400000) return 'status-soon';    // < 24h
    return 'status-ok';
  }

  render() {
    if (this._loading && !this._tokens.length) {
      return html`<ha-card><div class="loading">Loading...</div></ha-card>`;
    }

    return html`
      <ha-card>
        <div class="header">
          <h2>${this._config.title}</h2>
          <div class="mode-toggle">
            <span class="mode-label">Guest Mode</span>
            <ha-switch
              .checked=${this._modeActive}
              @change=${this._toggleMode}
            ></ha-switch>
          </div>
        </div>

        ${this._error ? html`<div class="error-banner">${this._error}</div>` : ''}

        ${this._modeActive ? html`
          <div class="mode-banner active">
            Guest mode active
            ${this._modeRemaining ? html`&mdash; ${this._modeRemaining} remaining` : ''}
          </div>
        ` : html`
          <div class="mode-banner inactive">Guest mode off</div>
        `}

        <!-- Active Tokens -->
        <div class="section">
          <div class="section-header">
            <h3>Active Tokens (${this._tokens.length})</h3>
            <ha-button
              @click=${() => this._showCreateForm = !this._showCreateForm}
            >+ New Token</ha-button>
          </div>

          ${this._showCreateForm ? this._renderCreateForm() : ''}
          ${this._newToken ? this._renderNewTokenResult() : ''}

          ${this._tokens.length === 0 ? html`
            <div class="empty-state">No active tokens. Create one to give guests access.</div>
          ` : this._tokens.map(t => this._renderToken(t))}
        </div>

        <!-- QR Code -->
        ${this._config.show_qr && this._guestUrl ? html`
          <div class="section qr-section">
            <h3>Guest Access QR</h3>
            <p class="qr-hint">Share this code for guests to scan</p>
            <img src="https://api.qrserver.com/v1/create-qr-code/?size=200x200&data=${encodeURIComponent(this._guestUrl)}"
                 alt="Guest access QR code" class="qr-code" />
            <div class="url-display">
              <input type="text" .value=${this._guestUrl} readonly />
              <ha-button @click=${() => this._copyToClipboard(this._guestUrl)}>Copy</ha-button>
            </div>
          </div>
        ` : ''}
      </ha-card>
    `;
  }

  _renderCreateForm() {
    return html`
      <form class="create-form" @submit=${this._createToken}>
        <label>
          <span>Label</span>
          <input type="text" name="label" placeholder="e.g. Plumber Wed" />
        </label>
        <label>
          <span>Duration (hours)</span>
          <input type="number" name="duration" value=${this._config.default_duration} min="1" max="8760" />
        </label>
        <label>
          <span>Entity scopes</span>
          <input type="text" name="entities" value="light.*" placeholder="light.*, lock.*" />
        </label>
        <label>
          <span>Domain scopes</span>
          <input type="text" name="domains" value="light,switch,climate" placeholder="light,switch,climate" />
        </label>
        <label>
          <span>Allowed services</span>
          <input type="text" name="services" placeholder="light.turn_on, lock.unlock" />
        </label>
        <div class="form-actions">
          <ha-button @click=${() => this._showCreateForm = false}>Cancel</ha-button>
          <ha-button variant="filled" type="submit">Create Token</ha-button>
        </div>
      </form>
    `;
  }

  _renderNewTokenResult() {
    if (!this._newToken) return '';
    return html`
      <div class="new-token-banner">
        <strong>Token created!</strong>
        <div class="token-detail">
          <span>Guest URL:</span>
          <input type="text" .value=${this._newToken.guest_url} readonly />
          <ha-button @click=${() => this._copyToClipboard(this._newToken.guest_url)}>Copy</ha-button>
        </div>
        <div class="token-detail">
          <span>Secret:</span>
          <input type="text" .value=${this._newToken.secret} readonly />
          <ha-button @click=${() => this._copyToClipboard(this._newToken.secret)}>Copy</ha-button>
        </div>
        <p class="token-warning">This is the only time the secret is shown. Save it now.</p>
      </div>
    `;
  }

  _renderToken(token) {
    const statusClass = this._getStatusClass(token);
    return html`
      <div class="token-card ${statusClass}">
        <div class="token-info">
          <div class="token-label">${token.label || 'Guest'}</div>
          <div class="token-meta">
            Expires ${this._formatExpiry(token.expires_at)}
            ${token.use_count > 0 ? html`&middot; ${token.use_count} uses` : ''}
          </div>
        </div>
        <div class="token-actions">
          <ha-button
            class="revoke-btn"
            @click=${() => this._revokeToken(token.token_id)}
          >Revoke</ha-button>
        </div>
      </div>
    `;
  }

  static get styles() {
    return css`
      :host { display: block; }
      ha-card { padding: 16px; }
      .header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 12px;
      }
      .header h2 { margin: 0; font-size: 1.2rem; }
      .mode-toggle { display: flex; align-items: center; gap: 8px; }
      .mode-label { font-size: 0.85rem; opacity: 0.7; }
      .mode-banner {
        padding: 10px 16px; border-radius: 8px; margin-bottom: 16px;
        font-weight: 500; font-size: 0.9rem;
      }
      .mode-banner.active { background: #1b5e20; color: #a5d6a7; }
      .mode-banner.inactive { background: #333; color: #999; }
      .section { margin-bottom: 16px; }
      .section-header {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 8px;
      }
      .section-header h3 { margin: 0; font-size: 1rem; }
      .empty-state { padding: 16px; text-align: center; opacity: 0.5; font-style: italic; }
      .token-card {
        display: flex; justify-content: space-between; align-items: center;
        padding: 10px 12px; background: #1e1e1e; border-radius: 8px; margin-bottom: 8px;
        border-left: 3px solid transparent;
      }
      .token-card.status-ok { border-left-color: #4caf50; }
      .token-card.status-soon { border-left-color: #ff9800; }
      .token-card.status-expiring { border-left-color: #f44336; }
      .token-card.status-revoked { opacity: 0.4; border-left-color: #666; }
      .token-label { font-weight: 500; }
      .token-meta { font-size: 0.8rem; opacity: 0.6; margin-top: 2px; }
      .create-form {
        background: #1e1e1e; border-radius: 8px; padding: 16px; margin-bottom: 12px;
      }
      .create-form label {
        display: block; margin-bottom: 10px;
      }
      .create-form label span {
        display: block; font-size: 0.8rem; opacity: 0.7; margin-bottom: 4px;
      }
      .create-form input {
        width: 100%; padding: 8px; border: 1px solid #333; border-radius: 6px;
        background: #2a2a2a; color: #eee; font-size: 0.85rem;
      }
      .form-actions {
        display: flex; justify-content: flex-end; gap: 8px; margin-top: 12px;
      }
      .new-token-banner {
        background: #1b5e20; border-radius: 8px; padding: 12px; margin-bottom: 12px;
      }
      .new-token-banner strong { color: #a5d6a7; }
      .token-detail {
        display: flex; align-items: center; gap: 8px; margin-top: 8px;
      }
      .token-detail span { font-size: 0.8rem; opacity: 0.7; white-space: nowrap; }
      .token-detail input {
        flex: 1; padding: 4px 8px; border: 1px solid #2e7d32; border-radius: 4px;
        background: #2a2a2a; color: #eee; font-size: 0.8rem;
      }
      .token-warning { font-size: 0.75rem; opacity: 0.6; margin-top: 8px; }
      .qr-section { text-align: center; }
      .qr-hint { font-size: 0.85rem; opacity: 0.6; }
      .qr-code { width: 200px; height: 200px; margin: 12px auto; border-radius: 8px; }
      .url-display {
        display: flex; gap: 8px; margin-top: 8px;
      }
      .url-display input {
        flex: 1; padding: 6px; border: 1px solid #333; border-radius: 6px;
        background: #2a2a2a; color: #eee; font-size: 0.8rem;
      }
      .error-banner {
        background: #b71c1c; color: #ef9a9a; padding: 8px 12px; border-radius: 6px;
        margin-bottom: 12px; font-size: 0.85rem;
      }
      .loading { padding: 24px; text-align: center; opacity: 0.5; }
    `;
  }
}

// HA uses getCardSize() to compute view layout. Without it the card defaults
// to size 1 and can be cropped or jammed against neighbouring cards.
GatekeeperCard.prototype.getCardSize = function () {
  const baseRows = 3; // header + toggle + section title
  const tokenRows = Math.max(1, (this._tokens || []).length);
  return baseRows + tokenRows + (this._guestUrl ? 2 : 0);
};

customElements.define('gatekeeper-card', GatekeeperCard);

// Register card type for HA
window.customCards = window.customCards || [];
window.customCards.push({
  type: 'gatekeeper-card',
  name: 'Gatekeeper',
  description: 'Manage guest access tokens and guest mode',
  preview: false,
});
