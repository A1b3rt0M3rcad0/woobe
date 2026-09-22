from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.tool_release_snapshots import (
    build_release_tool_runtime,
    tool_from_release_snapshot,
    tool_to_release_snapshot,
)
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import RiskLevel, ToolStatus, ToolType
from shared.infra.errors import ValidationError


def _tool(*, project_id=None, status=ToolStatus.ACTIVE) -> Tool:
    return Tool(
        project_id=project_id or uuid4(),
        name="Lookup customer",
        description="Fetch a customer record",
        type=ToolType.HTTP,
        config={
            "url": "https://example.com/customers/{{customer_id}}",
            "method": "GET",
            "headers": [{"key": "Authorization", "value": "{{secret:CUSTOMER_API_KEY}}"}],
        },
        input_schema={
            "type": "object",
            "properties": {"customer_id": {"type": "string"}},
            "required": ["customer_id"],
        },
        output_schema={"type": "object"},
        risk_level=RiskLevel.MEDIUM,
        timeout_ms=5000,
        status=status,
    )


def test_tool_release_snapshot_is_deeply_immutable_from_live_tool_changes():
    tool = _tool()
    snapshot = tool_to_release_snapshot(tool)

    tool.config["headers"][0]["value"] = "changed"
    tool.input_schema["properties"]["customer_id"]["type"] = "integer"

    assert snapshot["config"]["headers"][0]["value"] == "{{secret:CUSTOMER_API_KEY}}"
    assert snapshot["input_schema"]["properties"]["customer_id"]["type"] == "string"
    assert len(snapshot["snapshot_hash"]) == 64


def test_tool_release_snapshot_round_trip_preserves_runtime_config():
    tool = _tool()
    snapshot = tool_to_release_snapshot(tool)

    restored = tool_from_release_snapshot(snapshot)

    assert restored.id == tool.id
    assert restored.project_id == tool.project_id
    assert restored.type == ToolType.HTTP
    assert restored.config["url"] == tool.config["url"]
    assert restored.config["method"] == "GET"
    assert restored.config["headers"][0]["key"] == "Authorization"
    assert restored.config["headers"][0]["value"] == "{{secret:CUSTOMER_API_KEY}}"
    assert restored.input_schema["properties"] == tool.input_schema["properties"]
    assert restored.input_schema["required"] == ["customer_id"]
    assert restored.input_schema["additionalProperties"] is False
    assert restored.risk_level == RiskLevel.MEDIUM
    assert restored.timeout_ms == 5000


@pytest.mark.asyncio
async def test_build_release_tool_runtime_deduplicates_and_freezes_selected_tools():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    repo = AsyncMock()
    repo.get_by_id.return_value = tool

    runtime = await build_release_tool_runtime(
        repo,
        project_id=project_id,
        raw_tool_ids=[str(tool.id), tool.id],
    )

    assert runtime["tool_ids"] == [str(tool.id)]
    assert len(runtime["snapshots"]) == 1
    assert runtime["snapshots"][0]["id"] == str(tool.id)
    repo.get_by_id.assert_awaited_once_with(tool.id)


@pytest.mark.asyncio
async def test_build_release_tool_runtime_rejects_cross_project_tool():
    project_id = uuid4()
    tool = _tool(project_id=uuid4())
    repo = AsyncMock()
    repo.get_by_id.return_value = tool

    with pytest.raises(ValidationError, match="does not belong"):
        await build_release_tool_runtime(
            repo,
            project_id=project_id,
            raw_tool_ids=[tool.id],
        )


@pytest.mark.asyncio
async def test_build_release_tool_runtime_rejects_inactive_tool():
    project_id = uuid4()
    tool = _tool(project_id=project_id, status=ToolStatus.INACTIVE)
    repo = AsyncMock()
    repo.get_by_id.return_value = tool

    with pytest.raises(ValidationError, match="not active"):
        await build_release_tool_runtime(
            repo,
            project_id=project_id,
            raw_tool_ids=[tool.id],
        )


@pytest.mark.asyncio
async def test_build_release_tool_runtime_requires_every_external_context_field():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    tool.config["body"] = {
        "age": "{{external_context.age}}",
        "title": "{{external_context.title}}",
    }
    repo = AsyncMock()
    repo.get_by_id.return_value = tool

    with pytest.raises(ValidationError, match="title"):
        await build_release_tool_runtime(
            repo,
            project_id=project_id,
            raw_tool_ids=[tool.id],
            external_context_contract={
                "age": {
                    "schema": {"type": "integer"},
                    "required": False,
                    "model": {"expose": False},
                },
            },
        )


@pytest.mark.asyncio
async def test_build_release_tool_runtime_accepts_all_external_context_fields_even_if_hidden_or_optional():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    tool.config["body"] = {
        "age": "{{external_context.age}}",
        "title": "{{external_context.title}}",
    }
    repo = AsyncMock()
    repo.get_by_id.return_value = tool

    runtime = await build_release_tool_runtime(
        repo,
        project_id=project_id,
        raw_tool_ids=[tool.id],
        external_context_contract={
            "age": {
                "schema": {"type": "integer"},
                "required": False,
                "model": {"expose": False},
            },
            "title": {
                "schema": {"type": "string"},
                "required": False,
                "model": {"expose": False},
            },
        },
    )

    assert runtime["tool_ids"] == [str(tool.id)]


@pytest.mark.asyncio
async def test_build_release_tool_runtime_requires_existing_project_environment_keys():
    project_id = uuid4()
    tool = _tool(project_id=project_id)
    tool.config["headers"] = [
        {"key": "Authorization", "value": "Bearer {{project_env.CRM_TOKEN}}"},
    ]
    repo = AsyncMock()
    repo.get_by_id.return_value = tool
    project_environment_reader = AsyncMock()
    project_environment_reader.require_keys.side_effect = ValidationError(
        "Project Environment key(s) do not exist in this Project: CRM_TOKEN"
    )

    with pytest.raises(ValidationError, match="CRM_TOKEN"):
        await build_release_tool_runtime(
            repo,
            project_id=project_id,
            raw_tool_ids=[tool.id],
            project_environment_reader=project_environment_reader,
        )

    project_environment_reader.require_keys.assert_awaited_once_with(
        project_id=project_id,
        keys={"CRM_TOKEN"},
    )
