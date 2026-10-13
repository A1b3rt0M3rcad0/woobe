"""Configuration validation independent of storage, consumers and transport."""
from __future__ import annotations

import json
import re
from urllib.parse import urlsplit, urlunsplit, unquote

from shared.contracts.project_configuration import ConfigurationError

KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,127}$")
VALUE_FORMATS = frozenset({"string", "token", "json", "pem", "url"})
MAX_VALUE_BYTES = 262144
MAX_BATCH_SIZE = 50
VERSION_RETENTION_SECONDS = 7 * 24 * 60 * 60


def validate_declaration(key: str, kind: str, value_format: str, rules: dict) -> None:
    if (not isinstance(key, str) or not KEY_PATTERN.fullmatch(key)
            or not isinstance(kind, str) or kind not in {"secret", "value"}
            or not isinstance(value_format, str) or value_format not in VALUE_FORMATS
            or not isinstance(rules, dict)
            or set(rules) - {"min_length", "max_length", "allow_empty", "required_keys"}):
        raise ConfigurationError("CONFIG_DEFINITION_INVALID")
    for name in ("min_length", "max_length"):
        if name in rules and (type(rules[name]) is not int or not 0 <= rules[name] <= MAX_VALUE_BYTES):
            raise ConfigurationError("CONFIG_DEFINITION_INVALID")
    if rules.get("min_length", 0) > rules.get("max_length", MAX_VALUE_BYTES):
        raise ConfigurationError("CONFIG_DEFINITION_INVALID")
    if "allow_empty" in rules and type(rules["allow_empty"]) is not bool:
        raise ConfigurationError("CONFIG_DEFINITION_INVALID")
    required = rules.get("required_keys", [])
    if (not isinstance(required, list) or len(required) > 128
            or any(not isinstance(k, str) or not k or len(k) > 128 for k in required)
            or (required and value_format != "json")
            or (kind == "secret" and rules.get("allow_empty"))):
        raise ConfigurationError("CONFIG_DEFINITION_INVALID")


def validate_material(value: str, *, kind: str, value_format: str, rules: dict) -> None:
    """Validate without rewriting whitespace or putting the input in an error."""
    valid = isinstance(value, str)
    if valid:
        size = len(value.encode("utf-8"))
        minimum = max(rules.get("min_length", 0), 0 if kind == "value" and rules.get("allow_empty") else 1)
        valid = minimum <= size <= min(rules.get("max_length", MAX_VALUE_BYTES), MAX_VALUE_BYTES)
    if valid and value_format == "token":
        valid = bool(value.strip()) and not any(c in value for c in "\r\n\x00")
    if valid and value_format == "json":
        try:
            parsed = json.loads(value)
            valid = isinstance(parsed, dict) and all(k in parsed for k in rules.get("required_keys", []))
        except (ValueError, TypeError, RecursionError):
            valid = False
    if valid and value_format == "pem":
        valid = bool(re.fullmatch(r"\s*-----BEGIN ([A-Z0-9 ]+)-----\r?\n[A-Za-z0-9+/=\r\n]+-----END \1-----\s*", value))
    if valid and value_format == "url":
        try:
            canonical_destination(value)
        except ConfigurationError:
            valid = False
    if not valid:
        raise ConfigurationError("CONFIG_VALUE_INVALID")


def canonical_destination(value: str) -> str:
    """Identity used by grants; no wildcard, credentials, fragments or templates."""
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.fragment or parsed.query
                or any(c in value for c in "\r\n\x00{}\\")
                or any(s in {".", ".."} for s in parsed.path.split("/"))
                or "%" in parsed.netloc or "%2f" in parsed.path.lower()
                or "%2e" in parsed.path.lower()):
            raise ValueError
        decoded = parsed.path
        for _ in range(5):
            if any(fragment in decoded.lower() for fragment in ("%2f", "%2e", "%5c", "%00", "%0a", "%0d")):
                raise ValueError
            normalized = unquote(decoded)
            if normalized == decoded:
                break
            decoded = normalized
        else:
            raise ValueError
        host = parsed.hostname.encode("idna").decode("ascii").lower()
        if ":" in host:
            host = f"[{host}]"
        port = parsed.port
        default = 443 if parsed.scheme == "https" else 80
        authority = host + (f":{port}" if port is not None and port != default else "")
        return urlunsplit((parsed.scheme, authority, parsed.path.rstrip("/") or "/", "", ""))
    except (ValueError, UnicodeError, TypeError, AttributeError):
        raise ConfigurationError("CONFIG_BINDING_INVALID") from None



from shared.contracts.project_configuration import compile_authentication  # noqa: F401
