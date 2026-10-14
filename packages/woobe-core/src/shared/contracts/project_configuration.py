"""Versioned, transport-neutral Project configuration contracts.

These objects contain references and public diagnostics only. Plaintext and
ciphertext never belong in a dependency, lease, readiness result or receipt.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import UUID

from shared.contracts.errors import DomainError

CONFIGURATION_SCHEMA_VERSION = "project_configuration.v1"
Environment = Literal["draft", "staging", "production"]
SENSITIVE_AUTHENTICATION_HEADERS = frozenset({'authorization', 'proxy-authorization', 'x-api-key', 'api-key', 'cookie'})


def tool_configuration_permissions(config, *, compatibility_update=False):
    """Authority hints for authenticated owner writes; never value resolution."""
    if not isinstance(config, dict):
        return []
    routes = config.get('routes') if isinstance(config.get('routes'), list) else []
    scopes = [config.get('authentication'), *(route.get('authentication') for route in routes if isinstance(route, dict))]
    scopes = [scope for scope in scopes if scope is not None and scope != {'type': 'none'}
              and scope != {'type': 'none', 'fields': {}}]
    # Updates compare the current owner definition inside its locked transaction;
    # presence alone cannot distinguish a metadata round-trip from rebinding.
    permissions = [('project:environment:bind', None)] if scopes and not compatibility_update else []
    server = config.get('server') if isinstance(config.get('server'), dict) else {}
    headers = []
    for raw in [config.get('headers'), config.get('server_headers'), server.get('headers'),
                *(route.get('headers') for route in routes if isinstance(route, dict))]:
        if isinstance(raw, list):
            headers.extend(raw)
    inline = any(isinstance(row, dict) and row.get('mode') != 'remove'
        and (row.get('sensitive') is True or str(row.get('key', '')).lower() in SENSITIVE_AUTHENTICATION_HEADERS)
        and isinstance(row.get('value'), str) and bool(row['value']) and '{{' not in row['value']
        for row in headers)
    if inline:
        permissions.append(('project:environment:value:write', 'tool:write'))
    return permissions


def valid_tool_authentication_field(path):
    """Only explicit parent/route authentication fields can consume aliases."""
    import re
    return isinstance(path, str) and len(path) <= 512 and re.fullmatch(
        r"/config/(?:routes/(?:[^~/\r\n\x00]|~[01])+/)?authentication/fields/[!#$%&'*+.^_`|~0-9A-Za-z-]+",
        path,
    ) is not None
MaterialState = Literal["missing", "present", "invalid_format", "revoked", "unavailable"]


class ConfigurationError(DomainError):
    """An intentionally bounded diagnostic; never accepts request/value content."""

    def __init__(self, code: str, *, key: str | None = None, environment: str | None = None):
        messages = {
            "CONFIG_REFERENCE_NOT_FOUND": "Configuration reference does not exist in this Project",
            "CONFIG_KIND_MISMATCH": "Configuration kind is incompatible with the consumer",
            "CONFIG_VALUE_MISSING": "Required configuration value is not configured",
            "CONFIG_VALUE_INVALID": "Configuration value does not satisfy its declared format",
            "CONFIG_USAGE_NOT_AUTHORIZED": "Configuration use is not authorized for this consumer",
            "CONFIG_DESTINATION_CHANGED": "The connection destination has not been approved",
            "CONFIG_VALUE_REVOKED": "The pinned configuration value was revoked",
            "CONFIG_VERSION_UNAVAILABLE": "The pinned configuration version is no longer available",
            "CONFIG_REVISION_CONFLICT": "Configuration changed; reload metadata and review the change",
            "CONFIG_STORE_UNAVAILABLE": "Configuration status is temporarily unavailable",
            "CONFIG_REFERENCE_IN_USE": "Configuration is referenced by a retained resource definition",
            "CONFIG_BINDING_INVALID": "Configuration binding is invalid or includes an inline value",
            "CONFIG_DEFINITION_INVALID": "Configuration declaration is invalid",
            "LEGACY_ENVIRONMENT_REQUIRED": "Select an Environment after converting legacy configuration",
            "LEGACY_FORMAT_UNSUPPORTED": "Legacy configuration requires explicit review",
            "CONFIG_MIGRATION_WORK_PENDING": "Finish active Runs, vector builds and package operations; apply or expire pending package plans before cutover",
            "CONFIG_BRIDGE_REQUIRED": "Drain incompatible processes before configuration cutover",
        }
        if code not in messages:
            raise ValueError("Unknown configuration diagnostic")
        super().__init__(messages[code])
        self.code, self.key, self.environment = code, key, environment
        self.status_code = (503 if code == "CONFIG_STORE_UNAVAILABLE" else
                            403 if code == "CONFIG_USAGE_NOT_AUTHORIZED" else
                            422 if code in {"CONFIG_REFERENCE_NOT_FOUND", "CONFIG_KIND_MISMATCH",
                                           "CONFIG_VALUE_INVALID", "CONFIG_BINDING_INVALID",
                                           "CONFIG_DEFINITION_INVALID", "LEGACY_FORMAT_UNSUPPORTED"} else 409)


@dataclass(frozen=True, slots=True)
class ConfigurationDependency:
    project_id: UUID
    consumer_kind: str
    consumer_id: UUID
    definition_revision: str
    field_path: str
    key: str
    destination: str
    kind: str = "secret"
    required: bool = True
    legacy_alias_id: UUID | None = None
    impact: tuple[tuple[str, str], ...] = ()

    @property
    def identity(self) -> tuple[str, str, str, str]:
        return self.consumer_kind, str(self.consumer_id), self.field_path, self.key


@dataclass(frozen=True, slots=True)
class ConfigurationValuePin:
    key_id: UUID
    version: UUID
    environment: str
    source: str
    consumer_kind: str
    consumer_id: UUID
    field_path: str
    destination: str
    policy_revision: int
    policy_id: UUID
    alias_id: UUID | None = None

    def document(self) -> dict[str, Any]:
        from dataclasses import asdict
        return {name: str(value) if isinstance(value, UUID) else value
                for name, value in asdict(self).items()}


@dataclass(frozen=True, slots=True)
class ConfigurationIssue:
    code: str
    key: str
    environment: str
    consumer_kind: str
    consumer_id: str
    field_path: str
    remediation: dict[str, Any] = field(default_factory=dict)
    required_for: str = "execution"


def compile_authentication(value: dict, *, allow_none: bool = False, allow_legacy: bool = False) -> dict:
    import re
    key_pattern = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
    if not isinstance(value, dict) or set(value) - {"type", "fields"}:
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    kind, fields = value.get("type"), value.get("fields", {})
    allowed = {"api_key": {"api_key"}, "bearer": {"token"},
               "basic": {"username", "password"}, "headers": None}
    if kind == "none":
        if not allow_none or fields:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        return {"type": "none", "fields": {}}
    if (not isinstance(kind, str) or kind not in allowed or not isinstance(fields, dict) or not fields or len(fields) > 16
            or (allowed[kind] is not None and set(fields) != allowed[kind])):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    if kind == "headers" and len({str(name).lower() for name in fields}) != len(fields):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    result = {}
    for field, reference in fields.items():
        if (not isinstance(field, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,127}", field)
                or not isinstance(reference, dict)
                or not ((set(reference) == {"source", "key"} and reference.get("source") == "project_environment")
                    or (allow_legacy and set(reference) == {"source", "key", "alias_id"} and reference.get("source") == "legacy_configuration"))
                or not isinstance(reference["key"], str) or not key_pattern.fullmatch(reference["key"])):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        if kind == "headers" and field.lower() in {"host", "content-length", "transfer-encoding", "connection",
                "proxy-authorization", "proxy-connection", "forwarded", "x-forwarded-host", "x-forwarded-proto", "x-forwarded-for"}:
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        if reference["source"] == "legacy_configuration":
            try:
                UUID(str(reference["alias_id"]))
            except (ValueError, TypeError, AttributeError):
                raise ConfigurationError("CONFIG_BINDING_INVALID") from None
        result[field] = dict(reference)
    return {"type": kind, "fields": result}
