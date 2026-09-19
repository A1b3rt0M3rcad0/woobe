from __future__ import annotations

import re
from typing import Any, Mapping

_PROJECT_ENV_TEMPLATE_PATTERN = re.compile(
    r"\{\{\s*project_env\.([A-Za-z_][A-Za-z0-9_]*)\s*\}\}"
)
_PROJECT_ENV_KEY_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


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


__all__ = ["collect_tool_project_environment_keys"]
