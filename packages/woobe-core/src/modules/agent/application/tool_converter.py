from __future__ import annotations

from typing import Any

from modules.agent.application.interfaces.http_tool_contract import (
    allowed_http_group_routes,
    compile_http_group_route_contract,
    compile_http_tool_contract,
    is_http_tool_group,
)
from modules.agent.application.interfaces.tool_types import (
    HTTP_PROTOCOL,
    MCP_PROTOCOL,
    normalize_tool_protocol,
)
from modules.agent.application.tool_context_bindings import strip_bound_parameters
from modules.agent.domain.enums import ToolType
from modules.agent.domain.mcp_permissions import allowed_mcp_discovered_tools

MCP_PROVIDER_ROUTE_SEPARATOR = "::mcp::"


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
    exposes_server = (
        config.get("mode") == "server"
        or config.get("exposure") == "all_discovered"
    )
    return is_mcp and exposes_server


def _is_http_group_provider(tool: Any) -> bool:
    config = getattr(tool, "config", None) or {}
    tool_type = _type_value(getattr(tool, "type", None))
    return tool_type in {"http", "api", "webhook"} and is_http_tool_group(config)


def _mcp_provider_tool_definitions(
    tool: Any,
    used_names: set[str],
) -> tuple[list[dict], dict[str, str]]:
    config = getattr(tool, "config", None) or {}
    discovered_tools = allowed_mcp_discovered_tools(config)
    parent_name = _safe_tool_name(tool)
    definitions: list[dict] = []
    mapping: dict[str, str] = {}

    for discovered in discovered_tools:
        if not isinstance(discovered, dict):
            continue
        remote_name = discovered.get("name")
        if not isinstance(remote_name, str) or not remote_name.strip():
            continue
        function_name = _dedupe_name(
            _safe_name(f"{parent_name}_{remote_name}"),
            used_names,
        )
        parameters = discovered.get("input_schema") or discovered.get("inputSchema") or {
            "type": "object",
            "properties": {},
            "required": [],
        }
        if not isinstance(parameters, dict):
            parameters = {"type": "object", "properties": {}, "required": []}
        parameters = strip_bound_parameters(
            parameters,
            config,
            target_identifier=remote_name,
        )
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
        mapping[function_name] = (
            f"{tool.id}{MCP_PROVIDER_ROUTE_SEPARATOR}{remote_name}"
        )

    return definitions, mapping


def _http_provider_tool_definitions(
    tool: Any,
    used_names: set[str],
) -> tuple[list[dict], dict[str, str]]:
    config = getattr(tool, "config", None) or {}
    routes = allowed_http_group_routes(config)
    parent_name = _safe_tool_name(tool)
    parent_description = str(getattr(tool, "description", None) or "").strip()
    definitions: list[dict] = []
    mapping: dict[str, str] = {}

    for route in routes:
        route_id = str(route.get("id") or route.get("operation_id") or "").strip()
        operation_id = str(route.get("operation_id") or route_id).strip()
        if not route_id or not operation_id:
            continue
        function_name = _dedupe_name(
            _safe_name(f"{parent_name}_{operation_id}"),
            used_names,
        )
        parameters = compile_http_group_route_contract(
            config,
            route_id,
        ).input_schema
        parameters = strip_bound_parameters(
            parameters,
            config,
            target_identifier=route_id,
        )
        route_description = str(
            route.get("description") or route.get("name") or operation_id
        )
        description = route_description
        if parent_description:
            description = f"{route_description} Provider context: {parent_description}"
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
        mapping[function_name] = f"{tool.id}{MCP_PROVIDER_ROUTE_SEPARATOR}{route_id}"

    return definitions, mapping


def agent_tool_to_openai_definition(tool: Any) -> dict[str, Any]:
    config = getattr(tool, "config", None) or {}
    protocol = normalize_tool_protocol(getattr(tool, "type", None))
    name = _safe_tool_name(tool)

    if protocol == HTTP_PROTOCOL:
        if is_http_tool_group(config):
            return {
                "type": "function",
                "function": {
                    "name": name,
                    "description": getattr(tool, "description", None)
                    or "Grouped HTTP API",
                    "parameters": {
                        "type": "object",
                        "properties": {},
                        "required": [],
                    },
                },
            }
        contract = compile_http_tool_contract(
            config,
            getattr(tool, "input_schema", None),
        )
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": getattr(tool, "description", None)
                or f"HTTP {config.get('method', 'GET')} {config.get('url', '')}",
                "parameters": strip_bound_parameters(contract.input_schema, config),
            },
        }

    if protocol == MCP_PROTOCOL:
        server = config.get("server", {}) or {}
        input_schema = (
            getattr(tool, "input_schema", None)
            or config.get("discovered_input_schema")
            or config.get("input_schema")
            or {"type": "object", "properties": {}, "required": []}
        )
        tool_name = config.get("tool_name", "")
        server_name = server.get("name") or server.get("url") or "remote-server"
        return {
            "type": "function",
            "function": {
                "name": name,
                "description": getattr(tool, "description", None)
                or config.get("description")
                or f"MCP {server_name}/{tool_name}",
                "parameters": strip_bound_parameters(input_schema, config),
            },
        }

    return {
        "type": "function",
        "function": {
            "name": name,
            "description": getattr(tool, "description", None)
            or "Unsupported tool runtime",
            "parameters": getattr(tool, "input_schema", None)
            or {"type": "object", "properties": {}, "required": []},
        },
    }


def agent_tools_to_openai_definitions(tools: list) -> list[dict]:
    definitions, _mapping = agent_tools_to_openai_definitions_and_mapping(tools)
    return definitions


def agent_tools_to_openai_definitions_and_mapping(
    tools: list,
) -> tuple[list[dict], dict[str, str]]:
    definitions: list[dict] = []
    mapping: dict[str, str] = {}
    used_names: set[str] = set()

    for tool in tools:
        if _is_http_group_provider(tool):
            provider_definitions, provider_mapping = _http_provider_tool_definitions(
                tool,
                used_names,
            )
            definitions.extend(provider_definitions)
            mapping.update(provider_mapping)
            continue
        if _is_mcp_server_provider(tool):
            provider_definitions, provider_mapping = _mcp_provider_tool_definitions(
                tool,
                used_names,
            )
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
            definition = {
                **definition,
                "function": {
                    **definition.get("function", {}),
                    "name": unique_name,
                },
            }
        definitions.append(definition)
        mapping[unique_name] = str(tool.id)

    return definitions, mapping


def _safe_tool_name(tool: Any) -> str:
    return _safe_name(getattr(tool, "name", ""))
