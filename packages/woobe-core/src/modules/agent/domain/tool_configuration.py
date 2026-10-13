"""Typed Tool authentication references, separate from model-visible inputs."""
import hashlib
import json
from uuid import UUID
from shared.contracts.project_configuration import ConfigurationDependency, ConfigurationError, compile_authentication


def tool_authentication(config, *, allow_legacy=False):
    if not isinstance(config, dict) or "authentication" not in config:
        return None
    return compile_authentication(config["authentication"], allow_none=True, allow_legacy=allow_legacy)


def tool_dependencies(tool, *, impact=()):
    config = tool.config or {}
    auth = tool_authentication(config, allow_legacy=True)
    if auth is None or not auth["fields"]:
        return []
    destination = (config.get("server") or {}).get("url") or config.get("base_url") or config.get("url")
    if not isinstance(destination, str) or not destination or any(c in destination for c in "{}"):
        raise ConfigurationError("CONFIG_BINDING_INVALID")
    revision = hashlib.sha256(json.dumps({"authentication": auth, "destination": destination}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return [ConfigurationDependency(tool.project_id, "tool", tool.id, revision,
        "/config/authentication/fields/" + field, ref["key"], destination, impact=impact,
        legacy_alias_id=UUID(ref["alias_id"]) if ref["source"] == "legacy_configuration" else None)
        for field, ref in auth["fields"].items()]


def validate_tool_authentication(config):
    auth = tool_authentication(config)
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
