from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from modules.agent.application.interfaces.http_tool_contract import (
    http_group_route,
    is_http_tool_group,
)
from modules.agent.application.interfaces.tool_runtime import MCP_REMOTE_TOOL_INPUT_KEY


class ToolContextBindingError(ValueError):
    pass


def _normalize_bindings(raw: Any) -> dict[str, str]:
    if raw in (None, {}):
        return {}
    if not isinstance(raw, dict):
        raise ToolContextBindingError("Tool bindings must be an object")

    normalized: dict[str, str] = {}
    for raw_target, raw_binding in raw.items():
        target = str(raw_target).strip()
        if not target:
            raise ToolContextBindingError("Tool binding targets cannot be blank")
        if target == MCP_REMOTE_TOOL_INPUT_KEY:
            raise ToolContextBindingError(
                f"Tool binding target '{target}' is reserved by the runtime"
            )
        if not isinstance(raw_binding, dict):
            raise ToolContextBindingError(
                f"Tool binding '{target}' must be an object"
            )
        unknown = set(raw_binding) - {"source"}
        if unknown:
            names = ", ".join(sorted(str(item) for item in unknown))
            raise ToolContextBindingError(
                f"Tool binding '{target}' contains unknown properties: {names}"
            )
        source = raw_binding.get("source")
        if not isinstance(source, dict):
            raise ToolContextBindingError(
                f"Tool binding '{target}'.source must be an object"
            )
        unknown_source = set(source) - {"kind", "field"}
        if unknown_source:
            names = ", ".join(sorted(str(item) for item in unknown_source))
            raise ToolContextBindingError(
                f"Tool binding '{target}'.source contains unknown properties: {names}"
            )
        if source.get("kind") != "context":
            raise ToolContextBindingError(
                f"Tool binding '{target}'.source.kind must be 'context'"
            )
        field = str(source.get("field") or "").strip()
        if not field:
            raise ToolContextBindingError(
                f"Tool binding '{target}'.source.field cannot be blank"
            )
        normalized[target] = field
    return normalized


def _child_bindings(
    config: Mapping[str, Any],
    target_identifier: str | None,
) -> dict[str, str]:
    if not target_identifier:
        return {}

    if is_http_tool_group(dict(config)):
        route = http_group_route(dict(config), target_identifier)
        if isinstance(route, dict):
            return _normalize_bindings(route.get("bindings"))
        return {}

    exposes_server = (
        config.get("mode") == "server"
        or config.get("exposure") == "all_discovered"
    )
    if not exposes_server:
        return {}
    for discovered in config.get("discovered_tools") or []:
        if not isinstance(discovered, dict):
            continue
        if str(discovered.get("name") or "") == target_identifier:
            return _normalize_bindings(discovered.get("bindings"))
    return {}


def effective_context_bindings(
    config: Mapping[str, Any] | None,
    *,
    target_identifier: str | None = None,
) -> dict[str, str]:
    raw = dict(config or {})
    bindings = _normalize_bindings(raw.get("bindings"))
    bindings.update(_child_bindings(raw, target_identifier))
    return bindings


def apply_context_bindings(
    config: Mapping[str, Any] | None,
    input_data: Mapping[str, Any] | None,
    external_context_snapshot: Mapping[str, Any] | None,
) -> dict[str, Any]:
    runtime_input = dict(input_data or {})
    target_identifier = str(
        runtime_input.get(MCP_REMOTE_TOOL_INPUT_KEY) or ""
    ).strip() or None
    bindings = effective_context_bindings(
        config,
        target_identifier=target_identifier,
    )
    if not bindings:
        return runtime_input

    snapshot = dict(external_context_snapshot or {})
    for target, field in bindings.items():
        if field not in snapshot:
            raise ToolContextBindingError(
                f"External Context field '{field}' required by Tool binding '{target}' is unavailable"
            )
        # Runtime bindings are authoritative. Model-provided values cannot override
        # trusted application context.
        runtime_input[target] = deepcopy(snapshot[field])
    return runtime_input


def strip_bound_parameters(
    schema: Any,
    config: Mapping[str, Any] | None,
    *,
    target_identifier: str | None = None,
) -> dict[str, Any]:
    normalized_schema = (
        deepcopy(schema)
        if isinstance(schema, dict)
        else {"type": "object", "properties": {}, "required": []}
    )
    bindings = effective_context_bindings(
        config,
        target_identifier=target_identifier,
    )
    if not bindings:
        return normalized_schema

    properties = normalized_schema.get("properties")
    if isinstance(properties, dict):
        for target in bindings:
            properties.pop(target, None)
    required = normalized_schema.get("required")
    if isinstance(required, list):
        normalized_schema["required"] = [
            name for name in required if name not in bindings
        ]
    return normalized_schema


def validate_context_bindings(config: Mapping[str, Any] | None) -> None:
    raw = dict(config or {})
    _normalize_bindings(raw.get("bindings"))
    if is_http_tool_group(raw):
        for route in raw.get("routes") or []:
            if isinstance(route, dict):
                _normalize_bindings(route.get("bindings"))
    for discovered in raw.get("discovered_tools") or []:
        if isinstance(discovered, dict):
            _normalize_bindings(discovered.get("bindings"))


__all__ = [
    "ToolContextBindingError",
    "apply_context_bindings",
    "effective_context_bindings",
    "strip_bound_parameters",
    "validate_context_bindings",
]
