from uuid import uuid4

import pytest

from modules.agent.application.portable_export_tools import export_frozen_tool
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolType
from modules.agent.domain.mcp_permissions import normalize_permission
from modules.package.application.validation import validate_document
from shared.contracts.errors import ValidationError


def _tool(config, kind):
    return Tool(
        project_id=uuid4(),
        name="portable",
        description="Portable tool",
        type=kind,
        config=config,
        input_schema={"type": "object", "properties": {}},
        output_schema={"type": "object"},
    )


def test_mcp_export_keeps_desired_permissions_and_manual_bindings_without_oauth_or_cache():
    config = {
        "protocol": "mcp",
        "mode": "server",
        "exposure": "all_discovered",
        "server": {"url": "https://tools.example.test/mcp"},
        "input_schema_source": "discovered",
        "discovered_tools": [
            {
                "name": "lookup",
                "input_schema": {"type": "object"},
                "permission": {"mode": "deny"},
            }
        ],
        "discovered_input_schema": {"untrusted_cached": True},
        "oauth": {
            "access_token": "encrypted-private-oauth",
            "refresh_token": "private-refresh",
        },
        "discovery_state": "ready",
    }
    value = export_frozen_tool(tool_to_release_snapshot(_tool(config, ToolType.MCP)))
    assert value["permissions"] == [{"remote_name": "lookup", "permission": "deny"}]
    assert "discovered_tools" not in value["config"]
    assert "discovered_input_schema" not in value["config"]
    assert "oauth" not in value["config"]
    assert value["input_schema"] is None
    assert "encrypted-private-oauth" not in str(value)
    assert value["config"]["input_schema_source"] == "discovered"


def test_http_authentication_is_exportable_only_as_destination_reference():
    config = {
        "url": "https://tools.example.test/lookup",
        "headers": [{"key": "Authorization", "value": "Bearer {{secret:lookup-key}}"}],
    }
    value = export_frozen_tool(tool_to_release_snapshot(_tool(config, ToolType.HTTP)))
    assert value["config"]["headers"][0]["value"] == "Bearer {{secret:lookup-key}}"
    config["headers"][0]["value"] = "Bearer private-source-key"
    with pytest.raises(ValidationError, match="destination references"):
        export_frozen_tool(tool_to_release_snapshot(_tool(config, ToolType.HTTP)))


def test_url_credentials_are_rejected_without_echoing_authentication():
    tool = _tool(
        {"url": "https://user:private-key@tools.example.test/lookup"}, ToolType.HTTP
    )
    with pytest.raises(ValidationError) as failure:
        export_frozen_tool(tool_to_release_snapshot(tool))
    assert "private-key" not in str(failure.value)


def test_mcp_author_bindings_and_risk_export_as_remote_name_intent():
    tool = _tool(
        {
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"url": "https://mcp.test"},
            "discovered_tools": [
                {
                    "name": "lookup",
                    "permission": {"mode": "deny", "risk_level": "critical"},
                    "bindings": {
                        "tenant": {"source": {"kind": "context", "field": "tenant_id"}}
                    },
                }
            ],
        },
        ToolType.MCP,
    )
    value = export_frozen_tool(tool_to_release_snapshot(tool))
    assert value["permissions"] == [
        {
            "remote_name": "lookup",
            "permission": "deny",
            "risk": "critical",
            "bindings": {
                "tenant": {"source": {"kind": "context", "field": "tenant_id"}}
            },
        }
    ]
    assert "discovered_tools" not in value["config"]


def test_export_freezes_effective_root_risk_for_stable_policy_roundtrip():
    tool = _tool(
        {
            "url": "https://tools.example.test/lookup",
            "permission": {"mode": "deny", "risk_level": "high"},
        },
        ToolType.HTTP,
    )
    exported = export_frozen_tool(tool_to_release_snapshot(tool))
    assert exported["risk"] == "high"
    assert exported["config"]["permission"] == {"mode": "deny", "risk_level": "high"}
    default = export_frozen_tool(
        tool_to_release_snapshot(
            _tool({"url": "https://tools.example.test/lookup"}, ToolType.HTTP)
        )
    )
    assert default["config"]["permission"]["risk_level"] == default["risk"]


@pytest.mark.parametrize("mode", ["review", "deny", "allow"])
@pytest.mark.parametrize(
    "risk", ["unknown", "internal-sensitive", "low", "medium", "high", "critical", None]
)
def test_native_mcp_permission_risk_survives_export_schema_validation(mode, risk):
    native_permission = normalize_permission({"mode": mode, "risk_level": risk})
    tool = _tool(
        {
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"url": "https://mcp.test"},
            "discovered_tools": [{"name": "lookup", "permission": native_permission}],
        },
        ToolType.MCP,
    )
    exported = export_frozen_tool(tool_to_release_snapshot(tool))
    validated = validate_document(
        {
            "format": "woobe-package",
            "schema_version": "1.0",
            "kind": "Tool",
            "metadata": {"key": "lookup", "name": "Lookup"},
            "spec": {
                key: value
                for key, value in exported.items()
                if key not in {"id", "name"}
            },
        },
        "tool-1.yaml",
    )
    permission = validated.spec.permissions[0]
    assert permission.permission == mode
    assert permission.risk == native_permission.get("risk_level")
