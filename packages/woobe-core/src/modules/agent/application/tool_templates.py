from __future__ import annotations

import json
import re
from copy import deepcopy
from typing import Any, Mapping

_TEMPLATE_PATTERN = re.compile(
    r"\{\{\s*(external_context|project_env)\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
)


class ToolTemplateResolutionError(ValueError):
    pass


def collect_project_environment_keys(value: Any) -> set[str]:
    keys: set[str] = set()
    if isinstance(value, str):
        keys.update(
            match.group(2)
            for match in _TEMPLATE_PATTERN.finditer(value)
            if match.group(1) == "project_env"
        )
    elif isinstance(value, Mapping):
        for item in value.values():
            keys.update(collect_project_environment_keys(item))
    elif isinstance(value, (list, tuple)):
        for item in value:
            keys.update(collect_project_environment_keys(item))
    return keys


def _lookup(
    namespace: str,
    symbol: str,
    *,
    external_context: Mapping[str, Any],
    project_environment: Mapping[str, str],
) -> Any:
    if namespace == "external_context":
        if symbol not in external_context:
            raise ToolTemplateResolutionError(
                f"External Context field '{symbol}' required by Tool template is unavailable"
            )
        return deepcopy(external_context[symbol])

    if symbol not in project_environment:
        raise ToolTemplateResolutionError(
            f"Project Environment key '{symbol}' is not configured for this environment"
        )
    return project_environment[symbol]


def _string_value(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, bool, int, float)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)
    return str(value)


def _resolve_string(
    value: str,
    *,
    external_context: Mapping[str, Any],
    project_environment: Mapping[str, str],
) -> Any:
    full = _TEMPLATE_PATTERN.fullmatch(value)
    if full is not None:
        return _lookup(
            full.group(1),
            full.group(2),
            external_context=external_context,
            project_environment=project_environment,
        )

    def replace(match: re.Match[str]) -> str:
        resolved = _lookup(
            match.group(1),
            match.group(2),
            external_context=external_context,
            project_environment=project_environment,
        )
        return _string_value(resolved)

    return _TEMPLATE_PATTERN.sub(replace, value)


def resolve_tool_templates(
    value: Any,
    *,
    external_context: Mapping[str, Any] | None,
    project_environment: Mapping[str, str] | None,
) -> Any:
    """Resolve runtime-only Tool templates without mutating the persisted Tool."""

    external = external_context or {}
    environment = project_environment or {}

    if isinstance(value, str):
        return _resolve_string(
            value,
            external_context=external,
            project_environment=environment,
        )
    if isinstance(value, dict):
        resolved: dict[str, Any] = {}
        for key, item in value.items():
            candidate = item
            if key == "body" and isinstance(item, str):
                try:
                    parsed = json.loads(item)
                except (TypeError, ValueError):
                    parsed = None
                if isinstance(parsed, (dict, list)):
                    candidate = parsed
            resolved[key] = resolve_tool_templates(
                candidate,
                external_context=external,
                project_environment=environment,
            )
        return resolved
    if isinstance(value, list):
        return [
            resolve_tool_templates(
                item,
                external_context=external,
                project_environment=environment,
            )
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            resolve_tool_templates(
                item,
                external_context=external,
                project_environment=environment,
            )
            for item in value
        )
    return deepcopy(value)


__all__ = [
    "ToolTemplateResolutionError",
    "collect_project_environment_keys",
    "resolve_tool_templates",
]
