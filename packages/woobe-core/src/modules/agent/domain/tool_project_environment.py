from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping

_PROJECT_ENV_TEMPLATE_PATTERN = re.compile(
    r"\{\{\s*project_env\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
)
_EXTERNAL_CONTEXT_TEMPLATE_PATTERN = re.compile(
    r"\{\{\s*external_context\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
)
_PROJECT_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


@dataclass(frozen=True, slots=True)
class ToolRuntimeDependencies:
    external_context_fields: frozenset[str]
    project_environment_keys: frozenset[str]


def collect_tool_project_environment_keys(value: Any) -> set[str]:
    """Collect Project Environment keys referenced anywhere in a Tool config."""

    keys: set[str] = set()

    if isinstance(value, str):
        keys.update(
            match.group(1)
            for match in _PROJECT_ENV_TEMPLATE_PATTERN.finditer(value)
        )
        return keys

    if isinstance(value, Mapping):
        source = value.get("source")
        if isinstance(source, Mapping) and source.get("kind") == "project_environment":
            field = str(source.get("field") or "").strip()
            if _PROJECT_ENV_KEY_PATTERN.fullmatch(field):
                keys.add(field)

        for item in value.values():
            keys.update(collect_tool_project_environment_keys(item))
        return keys

    if isinstance(value, (list, tuple)):
        for item in value:
            keys.update(collect_tool_project_environment_keys(item))

    return keys


def collect_tool_external_context_fields(value: Any) -> set[str]:
    """Collect External Context fields referenced anywhere in a Tool config."""

    fields: set[str] = set()

    if isinstance(value, str):
        fields.update(
            match.group(1)
            for match in _EXTERNAL_CONTEXT_TEMPLATE_PATTERN.finditer(value)
        )
        return fields

    if isinstance(value, Mapping):
        source = value.get("source")
        if isinstance(source, Mapping) and source.get("kind") == "context":
            field = str(source.get("field") or "").strip()
            if field:
                fields.add(field)

        for item in value.values():
            fields.update(collect_tool_external_context_fields(item))
        return fields

    if isinstance(value, (list, tuple)):
        for item in value:
            fields.update(collect_tool_external_context_fields(item))

    return fields


def collect_tool_runtime_dependencies(value: Any) -> ToolRuntimeDependencies:
    return ToolRuntimeDependencies(
        external_context_fields=frozenset(
            collect_tool_external_context_fields(value)
        ),
        project_environment_keys=frozenset(
            collect_tool_project_environment_keys(value)
        ),
    )


__all__ = [
    "ToolRuntimeDependencies",
    "collect_tool_external_context_fields",
    "collect_tool_project_environment_keys",
    "collect_tool_runtime_dependencies",
]
