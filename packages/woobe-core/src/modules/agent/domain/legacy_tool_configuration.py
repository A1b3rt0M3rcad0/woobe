"""Compile migrated legacy header references for execution, never edit history."""
from copy import deepcopy
import re
from shared.contracts.project_configuration import ConfigurationError, compile_authentication

_REFERENCE = re.compile(r"\{\{secret:([^{}]+)\}\}")


def bind_legacy_tool_headers(tool, references):
    """References come exclusively from project-scoped Secret owner rows.

    A source-name lookup is not authorization: Core still requires the captured
    Tool/field relation, destination policy and Run lease at the real transport.
    """
    if not references:
        return tool
    result = deepcopy(tool)
    config = result.config or {}
    existing = config.get("authentication")
    fields = {}
    migrated = False
    authentication = None
    if existing is not None:
        authentication = compile_authentication(existing, allow_none=True, allow_legacy=True)
        if authentication["type"] == "headers":
            fields.update(authentication["fields"])

    def project(headers):
        nonlocal migrated
        remaining = []
        for row in headers or []:
            value = row.get("value", "")
            match = _REFERENCE.fullmatch(value) if isinstance(value, str) else None
            reference = references.get(match[1].strip()) if match else None
            if reference is None:
                remaining.append(row)
                continue
            migrated = True
            header = row.get("key")
            if not isinstance(header, str):
                raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
            old = next((name for name in fields if name.lower() == header.lower()), None)
            if old is not None and fields[old] != reference:
                raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
            fields[old or header] = deepcopy(reference)
        return remaining

    for owner, field in [(config, "headers"), (config, "server_headers"), (config.get("server") or {}, "headers")]:
        if field in owner:
            if not isinstance(owner[field], list):
                raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
            owner[field] = project(owner[field])
    for index, route in enumerate(config.get('routes', [])):
        route_names = legacy_tool_secret_names(route) & references.keys()
        if route_names:
            if not config.get('base_url') or not route.get('id') or not route.get('path'):
                raise ConfigurationError('LEGACY_FORMAT_UNSUPPORTED')
            # The route's base URL/path remains with the parent. This recursive
            # pass changes only its header authority, never promotes it globally.
            scoped = deepcopy(tool)
            scoped.config = route
            config['routes'][index] = bind_legacy_tool_headers(scoped, {name: references[name] for name in route_names}).config
            migrated = True
    if legacy_tool_secret_names(config) & references.keys():
        raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
    if not migrated:
        return tool
    if authentication is not None and authentication["type"] not in {"none", "headers"}:
        raise ConfigurationError("LEGACY_FORMAT_UNSUPPORTED")
    if fields:
        config["authentication"] = compile_authentication({"type": "headers", "fields": fields}, allow_legacy=True)
    result.config = config
    return result


def legacy_tool_secret_names(value):
    """Inventory recognized templates; never resolve or interpolate material."""
    if isinstance(value, str):
        return {match[1].strip() for match in _REFERENCE.finditer(value) if match[1].strip()}
    if isinstance(value, dict):
        return set().union(*(legacy_tool_secret_names(item) for item in value.values())) if value else set()
    if isinstance(value, (list, tuple)):
        return set().union(*(legacy_tool_secret_names(item) for item in value)) if value else set()
    return set()
