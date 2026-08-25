from __future__ import annotations

from modules.agent.domain.enums import ToolType

HTTP_PROTOCOL = "http"
MCP_PROTOCOL = "mcp"

HTTP_COMPATIBLE_TYPES = frozenset(
    {
        HTTP_PROTOCOL,
        ToolType.HTTP_MCP.value,
        ToolType.API.value,
        ToolType.WEBHOOK.value,
    }
)
MCP_COMPATIBLE_TYPES = frozenset({MCP_PROTOCOL})


def tool_type_value(tool_type: ToolType | str | None) -> str:
    if tool_type is None:
        return HTTP_PROTOCOL
    return tool_type.value if hasattr(tool_type, "value") else str(tool_type)


def normalize_tool_protocol(tool_type: ToolType | str | None) -> str:
    value = tool_type_value(tool_type)
    if value in HTTP_COMPATIBLE_TYPES:
        return HTTP_PROTOCOL
    if value in MCP_COMPATIBLE_TYPES:
        return MCP_PROTOCOL
    return value


def is_http_tool_type(tool_type: ToolType | str | None) -> bool:
    return normalize_tool_protocol(tool_type) == HTTP_PROTOCOL


def is_mcp_tool_type(tool_type: ToolType | str | None) -> bool:
    return normalize_tool_protocol(tool_type) == MCP_PROTOCOL
