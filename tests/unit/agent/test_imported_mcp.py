from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.imported_mcp import PrepareImportedMcpUseCase
from modules.agent.application.interfaces.imported_mcp import PreparedMcpInputs
from modules.agent.application.use_cases.commit_imported_mcp import (
    CommitImportedMcpUseCase,
)
from modules.agent.application.dtos.imported_mcp_dtos import CommitImportedMcpInput
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolType
from modules.agent.domain.imported_dependencies import ImportedDependencyPending
from tests.unit.agent.test_mcp_tool_refresh import FakeExecutor, FakeSecretResolver
from shared.contracts.errors import ConflictError, ValidationError
from shared.contracts.time import utc_now


def setup():
    tool = Tool(
        project_id=uuid4(),
        name="MCP",
        type=ToolType.MCP,
        config={
            "mode": "server",
            "exposure": "all_discovered",
            "server": {"url": "https://mcp.test"},
            "discovered_tools": [{"name": "cached", "permission": {"mode": "allow"}}],
        },
        updated_at=utc_now(),
    )
    prepared = PreparedMcpInputs(
        tool,
        tool.updated_at.isoformat(),
        FakeSecretResolver(),
        AsyncMock(return_value={}),
    )
    reader = SimpleNamespace(read=AsyncMock(return_value=prepared))
    executor = FakeExecutor()
    use_case = PrepareImportedMcpUseCase(reader, executor, None)
    return tool, reader, executor, use_case


@pytest.mark.asyncio
async def test_fresh_native_discovery_replaces_cached_tools_and_commits_under_revision_lock():
    tool, reader, executor, use_case = setup()
    incoming = await use_case.execute(
        project_id=tool.project_id,
        principal=object(),
        tool_id=tool.id,
        desired_permissions=[{"remote_name": "search", "permission": "allow"}],
    )
    assert [item["name"] for item in incoming["config"]["discovered_tools"]] == [
        "search"
    ]
    assert incoming["config"]["discovered_tools"][0]["permission"]["mode"] == "allow"
    assert len(executor.calls) >= 2
    persisted = Tool(
        project_id=tool.project_id,
        name="MCP",
        type=ToolType.MCP,
        updated_at=tool.updated_at,
    )
    persisted.updated_at = reader.read.return_value.tool.updated_at
    # Discovery changes the detached timestamp; the locked database resource must
    # still match the revision captured before any provider/MCP work.
    from datetime import datetime

    persisted.updated_at = datetime.fromisoformat(incoming["expected_revision"])
    repository = SimpleNamespace(
        lock_by_id=AsyncMock(return_value=persisted), update=AsyncMock()
    )
    result = await CommitImportedMcpUseCase(repository).execute(
        CommitImportedMcpInput.model_validate(incoming)
    )
    assert result["fresh_discovery"] is True and result["readiness"] == "ready"
    repository.update.assert_awaited_once()
    persisted.updated_at = utc_now()
    with pytest.raises(ConflictError, match="changed"):
        await CommitImportedMcpUseCase(repository).execute(
            CommitImportedMcpInput.model_validate(incoming)
        )


@pytest.mark.asyncio
async def test_oauth_wait_never_invokes_remote_or_trusts_cached_ready_state():
    tool, _, executor, use_case = setup()
    tool.config["mcp_status"] = "oauth_required"
    with pytest.raises(ImportedDependencyPending) as failure:
        await use_case.execute(
            project_id=tool.project_id,
            principal=object(),
            tool_id=tool.id,
            desired_permissions=[],
            require_ready=True,
        )
    assert failure.value.dependencies[0]["code"] == "MCP_OAUTH_REQUIRED"
    assert not executor.calls


@pytest.mark.asyncio
async def test_permissions_cannot_allow_a_remote_name_absent_from_fresh_discovery():
    tool, _, _, use_case = setup()
    with pytest.raises(ValidationError, match="fresh"):
        await use_case.execute(
            project_id=tool.project_id,
            principal=object(),
            tool_id=tool.id,
            desired_permissions=[{"remote_name": "cached", "permission": "allow"}],
        )


@pytest.mark.asyncio
async def test_author_bindings_and_risk_survive_fresh_discovery_without_cached_schema():
    tool, _, _, use_case = setup()
    binding = {"source": {"kind": "context", "field": "tenant_id"}}
    result = await use_case.execute(
        project_id=tool.project_id,
        principal=object(),
        tool_id=tool.id,
        desired_permissions=[
            {
                "remote_name": "search",
                "permission": "deny",
                "risk": "critical",
                "bindings": {"query": binding},
            }
        ],
    )
    remote = result["config"]["discovered_tools"][0]
    assert remote["name"] == "search"
    assert remote["permission"] == {"mode": "deny", "risk_level": "critical"}
    assert remote["bindings"] == {"query": binding}
    assert "cached" not in str(result["config"]["discovered_tools"])
