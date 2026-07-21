from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from modules.agent.application.http_tool_contract import compile_http_tool_group_contract
from modules.agent.application.tool_release_snapshots import build_release_tool_runtime
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType


class FakeToolRepository:
    def __init__(self, tool: Tool) -> None:
        self.tool = tool

    async def get_by_id(self, tool_id: UUID) -> Tool:
        assert tool_id == self.tool.id
        return self.tool


def http_group_config() -> dict:
    return {
        "protocol": "http",
        "mode": "group",
        "schema_version": 2,
        "base_url": "https://api.example.com",
        "routes": [
            {
                "id": "route-search",
                "operation_id": "search_employee",
                "name": "Search employee",
                "description": "Searches an employee by name.",
                "method": "GET",
                "path": "/employees",
                "risk_level": "low",
                "status": "active",
                "default_permission": "review",
            },
            {
                "id": "route-delete",
                "operation_id": "delete_employee",
                "name": "Delete employee",
                "description": "Deletes an employee record.",
                "method": "DELETE",
                "path": "/employees/{{employee_id}}",
                "risk_level": "high",
                "status": "active",
                "default_permission": "review",
            },
        ],
    }


@pytest.mark.asyncio
async def test_draft_runtime_persists_http_route_permissions_explicitly_and_in_snapshot() -> None:
    project_id = uuid4()
    compiled = compile_http_tool_group_contract(http_group_config())
    tool = Tool(
        id=uuid4(),
        project_id=project_id,
        name="Employees API",
        description="Employee operations.",
        type=ToolType.HTTP,
        config=compiled.config,
        risk_level=RiskLevel.HIGH,
        status=ToolStatus.ACTIVE,
    )
    raw_permissions = {
        str(tool.id): {
            "route-search": {"mode": "allow", "risk_level": "low"},
            "route-delete": {"mode": "deny", "risk_level": "high"},
        }
    }

    runtime = await build_release_tool_runtime(
        FakeToolRepository(tool),
        project_id=project_id,
        raw_tool_ids=[tool.id],
        raw_permissions=raw_permissions,
    )

    persisted = runtime["permissions"][str(tool.id)]
    assert persisted["route-search"] == {"mode": "allow", "risk_level": "low"}
    assert persisted["route-delete"] == {"mode": "deny", "risk_level": "high"}

    snapshot_routes = {
        route["id"]: route
        for route in runtime["snapshots"][0]["config"]["routes"]
    }
    assert snapshot_routes["route-search"]["permission"]["mode"] == "allow"
    assert snapshot_routes["route-delete"]["permission"]["mode"] == "deny"
