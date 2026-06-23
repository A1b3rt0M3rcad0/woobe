from __future__ import annotations

from typing import Any

from modules.agent.application.tool_runtime import build_default_tool_runtime_registry
from modules.agent.domain.enums import ToolType

MCP_PROVIDER_ROUTE_SEPARATOR = "::mcp::"


class _DefinitionOnlyExecutor:
    async def execute(self, *args, **kwargs):  # pragma: no cover - never called by definition building
        raise RuntimeError("Definition-only executor cannot run tools")


def _safe_name(value: str) -> str:
    name = str(value).lower().strip().replace(" ", "_").replace("-", "_")
    name = "".join(c for c in name if c.isalnum() or c == "_")
    if not name or name[0].isdigit():
        name = f"tool_{name}"
    return name


def _dedupe_name(name: str, used: set[str]) -> str:
    candidate = name
    suffix = 2
    while candidate in used:
        candidate = f"{name}_{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def _type_value(value: Any) -> str:
    if value is None:
        return ""
    raw_value = getattr(value, "value", value)
    return str(raw_value).lower()


def _is_mcp_server_provider(tool: Any) -> bool:
    config = getattr(tool, "config", None) or {}
    tool_type = getattr(tool, "type", None)
    is_mcp = (
        str(config.get("protocol") or "").lower() == "mcp"
        or tool_type in {ToolType.MCP, ToolType.HTTP_MCP}
        or _type_value(tool_type) in {"mcp", "http_mcp"}
    )
    exposes_server = config.get("mode") == "server" or config.get("exposure") == "all_discovered"
    return is_mcp and exposes_server


def _mcp_provider_tool_definitions(tool: Any, used_names: set[str]) -> tuple[list[dict], dict[str, str]]:
    config = getattr(tool, "config", None) or {}
    discovered_tools = config.get("discovered_tools") or []
    parent_name = _safe_tool_name(tool)
    definitions: list[dict] = []
    mapping: dict[str, str] = {}

    for discovered in discovered_tools:
        if not isinstance(discovered, dict):
            continue
        remote_name = discovered.get("name")
        if not isinstance(remote_name, str) or not remote_name.strip():
            continue
        function_name = _dedupe_name(_safe_name(f"{parent_name}_{remote_name}"), used_names)
        parameters = discovered.get("input_schema") or discovered.get("inputSchema") or {
            "type": "object",
            "properties": {},
            "required": [],
        }
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}, "required": []}
        description = (
            discovered.get("description")
            or getattr(tool, "description", None)
            or f"MCP tool {remote_name} from {getattr(tool, 'name', 'server')}"
        )
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": function_name,
                    "description": description,
                    "parameters": parameters,
                },
            }
        )
        mapping[function_name] = f"{tool.id}{MCP_PROVIDER_ROUTE_SEPARATOR}{remote_name}"

    return definitions, mapping


def agent_tool_to_openai_definition(tool) -> dict:
    registry = build_default_tool_runtime_registry(_DefinitionOnlyExecutor())
    return registry.to_openai_definition(tool)


def agent_tools_to_openai_definitions(tools: list) -> list[dict]:
    definitions, _mapping = agent_tools_to_openai_definitions_and_mapping(tools)
    return definitions


def agent_tools_to_openai_definitions_and_mapping(tools: list) -> tuple[list[dict], dict[str, str]]:
    definitions: list[dict] = []
    mapping: dict[str, str] = {}
    used_names: set[str] = set()

    for tool in tools:
        if _is_mcp_server_provider(tool):
            provider_definitions, provider_mapping = _mcp_provider_tool_definitions(tool, used_names)
            definitions.extend(provider_definitions)
            mapping.update(provider_mapping)
            continue

        definition = agent_tool_to_openai_definition(tool)
        function_name = definition.get("function", {}).get("name")
        if not isinstance(function_name, str) or not function_name:
            function_name = _safe_tool_name(tool)
            definition.setdefault("function", {})["name"] = function_name
        unique_name = _dedupe_name(function_name, used_names)
        if unique_name != function_name:
            definition = {**definition, "function": {**definition.get("function", {}), "name": unique_name}}
        definitions.append(definition)
        mapping[unique_name] = str(tool.id)

    return definitions, mapping


def _safe_tool_name(tool) -> str:
    return _safe_name(getattr(tool, "name", ""))
