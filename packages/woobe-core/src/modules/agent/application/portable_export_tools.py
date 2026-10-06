"""Export author configuration and binding intent without transport authentication."""

from copy import deepcopy

from modules.agent.application.dtos.tools_dtos import HttpToolConfig, McpToolConfig
from modules.agent.application.portable_authentication import (
    validate_portable_tool_authentication,
)
from modules.agent.application.tool_release_snapshots import tool_from_release_snapshot
from modules.agent.application.tool_types import is_http_tool_type, is_mcp_tool_type
from shared.contracts.errors import ValidationError


def export_frozen_tool(snapshot):
    tool = tool_from_release_snapshot(snapshot)
    raw = deepcopy(tool.config or {})
    if is_http_tool_type(tool.type):
        kind = "http"
        config = HttpToolConfig.model_validate(raw).model_dump(
            mode="json", exclude_none=True
        )
        permissions = []
    elif is_mcp_tool_type(tool.type):
        kind = "mcp"
        config = McpToolConfig.model_validate(raw).model_dump(
            mode="json", exclude_none=True
        )
        # Remote schema/cache and OAuth runtime state are destination discoveries.
        # Only desired names/permissions and manual author bindings cross projects.
        permissions = [
            {
                "remote_name": item["name"],
                **(
                    {"bindings": deepcopy(item["bindings"])}
                    if item.get("bindings")
                    else {}
                ),
                "permission": (item.get("permission") or {}).get("mode", "review"),
                **(
                    {"risk": item["permission"]["risk_level"]}
                    if (item.get("permission") or {}).get("risk_level") is not None
                    else {}
                ),
            }
            for item in config.pop("discovered_tools", [])
        ]
        config.pop("discovered_input_schema", None)
        config["server"].pop("command", None)
        config["server"].pop("args", None)
    else:
        raise ValidationError("Tool protocol has no portable native contract")
    validate_portable_tool_authentication(config)
    return {
        "id": str(tool.id),
        "name": tool.name,
        "description": tool.description or "",
        "type": kind,
        "config": config,
        "input_schema": deepcopy(tool.input_schema)
        if kind == "http" or config.get("input_schema_source") == "manual"
        else None,
        "output_schema": deepcopy(tool.output_schema),
        "timeout_ms": tool.timeout_ms or 10000,
        "risk": getattr(tool.risk_level, "value", tool.risk_level),
        "permission": (config.get("permission") or {}).get("mode", "allow"),
        "permissions": permissions,
    }
