from __future__ import annotations

from contextvars import ContextVar
from typing import Any
from uuid import UUID

RUNTIME_TOOL_INVENTORY_NAME = "woobe_list_available_tools"
RUNTIME_TOOL_INVENTORY_UUID = UUID("00000000-0000-4000-8000-00000000f001")

_current_runtime_tool_inventory: ContextVar[list[dict[str, Any]]] = ContextVar(
    "woobe_runtime_tool_inventory",
    default=[],
)


def runtime_tool_inventory_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": RUNTIME_TOOL_INVENTORY_NAME,
            "description": (
                "Call this tool before answering when the user asks what tools, MCP "
                "providers, integrations, external access, or runtime capabilities are "
                "available. This tool lists only the current agent runtime tools; do "
                "not use it to execute external work."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "filter": {
                        "type": "string",
                        "description": (
                            "Optional provider, tool, or capability to check, such as "
                            "DeepWiki, MCP, GitHub, repository access, browser, or database."
                        ),
                    },
                },
                "required": [],
            },
        },
    }


def _tool_name(definition: dict[str, Any]) -> str:
    name = definition.get("function", {}).get("name")
    return name if isinstance(name, str) else ""


def _tool_description(definition: dict[str, Any]) -> str:
    description = definition.get("function", {}).get("description")
    return description if isinstance(description, str) else ""


def _visible_tool_summary(definitions: list[dict[str, Any]]) -> list[dict[str, str]]:
    visible: list[dict[str, str]] = []
    for definition in definitions:
        name = _tool_name(definition)
        if not name or name == RUNTIME_TOOL_INVENTORY_NAME:
            continue
        visible.append(
            {
                "name": name,
                "description": _tool_description(definition)[:240],
            }
        )
    return visible


def set_runtime_tool_inventory(definitions: list[dict[str, Any]]) -> None:
    _current_runtime_tool_inventory.set(_visible_tool_summary(definitions))


def append_runtime_inventory_tool(
    definitions: list[dict[str, Any]],
    mapping: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, str]]:
    visible_tools = _visible_tool_summary(definitions)
    _current_runtime_tool_inventory.set(visible_tools)
    if not visible_tools:
        return definitions, mapping

    if any(_tool_name(definition) == RUNTIME_TOOL_INVENTORY_NAME for definition in definitions):
        return definitions, mapping

    next_definitions = [*definitions, runtime_tool_inventory_definition()]
    next_mapping = {**mapping, RUNTIME_TOOL_INVENTORY_NAME: str(RUNTIME_TOOL_INVENTORY_UUID)}
    return next_definitions, next_mapping


def is_runtime_tool_inventory_id(tool_id: UUID | str) -> bool:
    return str(tool_id) == str(RUNTIME_TOOL_INVENTORY_UUID)


def execute_runtime_tool_inventory(input_data: dict[str, Any] | None = None) -> dict[str, Any]:
    args = input_data or {}
    raw_filter = args.get("filter")
    filter_text = raw_filter.strip().lower() if isinstance(raw_filter, str) else ""

    tools = list(_current_runtime_tool_inventory.get())
    if filter_text:
        matched_tools = [
            tool
            for tool in tools
            if filter_text in tool.get("name", "").lower()
            or filter_text in tool.get("description", "").lower()
        ]
    else:
        matched_tools = tools

    result = {
        "has_tools": bool(tools),
        "matched": bool(matched_tools) if filter_text else bool(tools),
        "filter": raw_filter if isinstance(raw_filter, str) else None,
        "tools_count": len(matched_tools),
        "tools": matched_tools,
    }
    return {"success": True, "result": result}
