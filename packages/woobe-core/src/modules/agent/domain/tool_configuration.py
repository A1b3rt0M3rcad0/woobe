"""Typed Tool authentication references, separate from model-visible inputs."""
import hashlib
import json
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, compile_authentication


def tool_authentication(config, *, allow_legacy=False):
    if not isinstance(config, dict) or "authentication" not in config:
        return None
    return compile_authentication(config["authentication"], allow_none=True, allow_legacy=allow_legacy)


def tool_destination(value):
    """Static scheme/authority/path boundary; rendered sends are checked again.

    Parameterized paths require approval of their containing static path. URL
    query parameters do not define credential authority. Scheme/host templates
    are never credentials destinations.
    """
    import re
    if not isinstance(value, str) or not value or any(c in value for c in '\r\n\x00\\'):
        raise ConfigurationError('CONFIG_BINDING_INVALID')
    try:
        parsed = urlsplit(value)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname or parsed.username is not None
                or parsed.password is not None or parsed.fragment or any(c in parsed.netloc for c in '{}%')):
            raise ValueError
        path = parsed.path
        templates = list(re.finditer(r'\{\{[A-Za-z_][A-Za-z0-9_.]*\}\}', path))
        if any(c in re.sub(r'\{\{[A-Za-z_][A-Za-z0-9_.]*\}\}', '', path) for c in '{}'):
            raise ValueError
        if templates:
            prefix = path[:templates[0].start()]
            path = prefix[:prefix.rfind('/') + 1]
        # The central owner canonicalizes this boundary and rejects traversal,
        # encoded separators and malformed ports before storing a reference.
        return urlunsplit((parsed.scheme, parsed.netloc, path or '/', '', ''))
    except (ValueError, TypeError):
        raise ConfigurationError('CONFIG_BINDING_INVALID') from None


def tool_dependencies(tool, *, impact=()):
    config = tool.config or {}
    auth = tool_authentication(config, allow_legacy=True)
    if auth is None or not auth["fields"]:
        return []
    destination = (config.get("server") or {}).get("url") or config.get("base_url") or config.get("url")
    revision = hashlib.sha256(json.dumps({"authentication": auth, "destination": destination}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    destination = tool_destination(destination)
    return [ConfigurationDependency(tool.project_id, "tool", tool.id, revision,
        "/config/authentication/fields/" + field, ref["key"], destination, impact=impact,
        legacy_alias_id=UUID(ref["alias_id"]) if ref["source"] == "legacy_configuration" else None)
        for field, ref in auth["fields"].items()]


def validate_tool_authentication(config, *, allow_legacy=False):
    auth = tool_authentication(config, allow_legacy=allow_legacy)
    if auth is None:
        return
    # Mixing two authentication authorities is ambiguous, even if one is legacy.
    if config.get("auth") not in (None, {"type": "none"}) or config.get("oauth"):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    names = {"authorization", "proxy-authorization", "x-api-key"}
    if auth["type"] == "headers":
        names |= {name.lower() for name in auth["fields"]}
    def header_rows(raw):
        if isinstance(raw, dict):
            return [{"key": key, "value": value} for key, value in raw.items()]
        if raw is None:
            return []
        if not isinstance(raw, list) or any(not isinstance(row, dict) for row in raw):
            raise ConfigurationError("CONFIG_BINDING_INVALID")
        return raw
    headers = [*header_rows(config.get("headers")), *header_rows(config.get("server_headers")), *header_rows((config.get("server") or {}).get("headers"))]
    for route in config.get("routes", []):
        headers.extend(header_rows(route.get("headers")))
    if any(str(header.get("key", "")).lower() in names for header in headers):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    # Remote references cannot be copied into prompts, bodies, schemas or URLs.
    def scan(value):
        if isinstance(value, dict):
            if value.get("source") == "project_environment":
                raise ConfigurationError("CONFIG_BINDING_INVALID")
            for item in value.values():
                scan(item)
        elif isinstance(value, list):
            for item in value:
                scan(item)
        elif isinstance(value, str):
            import re
            if re.search(r"\{\{\s*secret\s*:", value):
                raise ConfigurationError("CONFIG_BINDING_INVALID")
    scan({key: value for key, value in config.items() if key != "authentication"})
