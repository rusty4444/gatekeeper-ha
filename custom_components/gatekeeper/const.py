"""Constants for Gatekeeper HA integration."""

DOMAIN = "gatekeeper"
MANUFACTURER = "Gatekeeper HA"

# Storage
STORAGE_KEY = f"{DOMAIN}.tokens"
STORAGE_VERSION = 1

# Config flow defaults
DEFAULT_EXPIRY_HOURS = 24
DEFAULT_AUTO_DISABLE_HOURS = 48
DEFAULT_GUEST_PAGE_PORT = 8921

# Token defaults
TOKEN_BYTE_LENGTH = 32  # secrets.token_urlsafe length
TOKEN_ID_LENGTH = 12    # ID prefix length
BCRYPT_ROUNDS = 12

# Events
EVENT_MODE_STARTED = f"{DOMAIN}_mode_started"
EVENT_MODE_ENDED = f"{DOMAIN}_mode_ended"
EVENT_TOKEN_CREATED = f"{DOMAIN}_token_created"
EVENT_TOKEN_REVOKED = f"{DOMAIN}_token_revoked"

# Services
SERVICE_CREATE_TOKEN = "create_token"
SERVICE_REVOKE_TOKEN = "revoke_token"
SERVICE_ACTIVATE_MODE = "activate_mode"
SERVICE_DEACTIVATE_MODE = "deactivate_mode"
SERVICE_GET_TOKENS = "get_tokens"
SERVICE_GET_GUEST_URL = "get_guest_url"

# Attributes
ATTR_TOKEN_ID = "token_id"
ATTR_LABEL = "label"
ATTR_EXPIRES_AT = "expires_at"
ATTR_DURATION = "duration"  # in hours
ATTR_SCOPED_ENTITIES = "scoped_entities"
ATTR_SCOPED_DOMAINS = "scoped_domains"
ATTR_ALLOWED_SERVICES = "allowed_services"
ATTR_MAX_USES = "max_uses"
ATTR_AUTO_DISABLE_AFTER = "auto_disable_after"  # in hours, 0 = manual only
ATTR_DISABLE_AUTOMATIONS = "disable_automations"
ATTR_AUTOMATION_ENTITY_IDS = "automation_entity_ids"
ATTR_SET_SAFE_STATES = "set_safe_states"
ATTR_DISABLE_SCRIPTS = "disable_scripts"
ATTR_DISABLE_SCENES = "disable_scenes"
ATTR_SAFE_STATE_OVERRIDES = "safe_state_overrides"  # dict of entity_id -> state dict

# Sensor / entity constants
SENSOR_TOKENS = f"{DOMAIN}_active_tokens"
SENSOR_SOONEST_EXPIRY = f"{DOMAIN}_soonest_expiry"
BINARY_SENSOR_MODE = f"{DOMAIN}_mode_active"
COORDINATOR_UPDATE_INTERVAL = 30  # seconds

# Guest mode states
MODE_OFF = "off"
MODE_ON = "on"

# Explicit re-export list so `from .const import *` is well-defined and
# linters/static analyzers can audit the surface. Add new constants here when
# they need to be imported by other modules.
__all__ = [
    "DOMAIN",
    "MANUFACTURER",
    "STORAGE_KEY",
    "STORAGE_VERSION",
    "DEFAULT_EXPIRY_HOURS",
    "DEFAULT_AUTO_DISABLE_HOURS",
    "DEFAULT_GUEST_PAGE_PORT",
    "TOKEN_BYTE_LENGTH",
    "TOKEN_ID_LENGTH",
    "BCRYPT_ROUNDS",
    "EVENT_MODE_STARTED",
    "EVENT_MODE_ENDED",
    "EVENT_TOKEN_CREATED",
    "EVENT_TOKEN_REVOKED",
    "SERVICE_CREATE_TOKEN",
    "SERVICE_REVOKE_TOKEN",
    "SERVICE_ACTIVATE_MODE",
    "SERVICE_DEACTIVATE_MODE",
    "SERVICE_GET_TOKENS",
    "SERVICE_GET_GUEST_URL",
    "ATTR_TOKEN_ID",
    "ATTR_LABEL",
    "ATTR_EXPIRES_AT",
    "ATTR_DURATION",
    "ATTR_SCOPED_ENTITIES",
    "ATTR_SCOPED_DOMAINS",
    "ATTR_ALLOWED_SERVICES",
    "ATTR_MAX_USES",
    "ATTR_AUTO_DISABLE_AFTER",
    "ATTR_DISABLE_AUTOMATIONS",
    "ATTR_AUTOMATION_ENTITY_IDS",
    "ATTR_SET_SAFE_STATES",
    "ATTR_DISABLE_SCRIPTS",
    "ATTR_DISABLE_SCENES",
    "ATTR_SAFE_STATE_OVERRIDES",
    "SENSOR_TOKENS",
    "SENSOR_SOONEST_EXPIRY",
    "BINARY_SENSOR_MODE",
    "COORDINATOR_UPDATE_INTERVAL",
    "MODE_OFF",
    "MODE_ON",
]
