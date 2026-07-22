from __future__ import annotations

from copy import deepcopy
from typing import Any


def constrain_tool_references(
    schema: dict[str, Any],
    *,
    allowed_names: list[str],
) -> dict[str, Any]:
    constrained = deepcopy(schema)
    try:
        tools = (
            constrained["properties"]["cases"]["items"]["properties"]
            ["expected_contract"]["properties"]["tools"]["properties"]
        )
    except (KeyError, TypeError):
        return constrained

    names = sorted({str(name).strip() for name in allowed_names if str(name).strip()})
    for field in ("required", "forbidden"):
        tool_list = dict(tools.get(field) or {})
        if names:
            tool_list["items"] = {"type": "string", "enum": names}
            tool_list["uniqueItems"] = True
        else:
            tool_list["items"] = {"type": "string"}
            tool_list["maxItems"] = 0
        tools[field] = tool_list
    return constrained


__all__ = ["constrain_tool_references"]
