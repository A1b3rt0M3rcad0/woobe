from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from modules.agent.application.portable_definition import (
    inspect_proposed_provider_model,
)
from modules.agent.application.use_cases.verify_imported_agent import (
    VerifyImportedAgentUseCase,
)
from modules.agent.application.tool_release_snapshots import tool_to_release_snapshot
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import (
    ToolType,
    AgentStatus,
    CredentialStatus,
    ProviderModelStatus,
)
from shared.contracts.errors import ConflictError


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "changed",
    ["inactive_model", "model_spec", "inactive_tool", "changed_tool", "inactive_existing", "archived_existing", "ready"],
)
async def test_import_verification_requires_live_models_and_exact_tools(
    monkeypatch, changed
):
    project, agent_id, draft_id, credential_id, model_id = (uuid4() for _ in range(5))
    model = inspect_proposed_provider_model(
        project_id=project,
        metadata={"name": "Fake"},
        spec={"provider": "custom", "model": "fake"},
    )
    provider_model = SimpleNamespace(
        project_id=project,
        provider_credential_id=credential_id,
        status=ProviderModelStatus.active,
        spec=model["spec"],
        spec_hash=model["spec_hash"],
    )
    tool = Tool(
        project_id=project,
        name="Lookup",
        type=ToolType.HTTP,
        config={"url": "https://tool.test"},
    )
    draft = SimpleNamespace(
        id=draft_id,
        project_id=project,
        agent_id=agent_id,
        snapshot_kind="draft",
        provider_credential_id=credential_id,
        fallback_credential_id=None,
        provider_model_id=model_id,
        fallback_provider_model_id=None,
        model_spec_snapshot=model["spec"],
        model_spec_hash=model["spec_hash"],
        runtime_config={
            "tools": {
                "tool_ids": [str(tool.id)],
                "snapshots": [tool_to_release_snapshot(tool)],
            }
        },
    )
    agent = SimpleNamespace(project_id=project, id=agent_id, status=AgentStatus.active)
    monkeypatch.setattr(
        "modules.agent.application.use_cases.verify_imported_agent.build_agent_execution_snapshot",
        lambda _: {},
    )
    if changed == "inactive_model":
        provider_model.status = ProviderModelStatus.inactive
    if changed == "model_spec":
        provider_model.spec = {**model["spec"], "model_id": "changed"}
    if changed == "inactive_tool":
        tool.status = "inactive"
    if changed == "changed_tool":
        tool.config = {"url": "https://different.test"}
    if changed == "inactive_existing":
        agent.status = AgentStatus.inactive
    if changed == "archived_existing":
        agent.status = AgentStatus.archived
    case = VerifyImportedAgentUseCase(
        SimpleNamespace(get_by_id=AsyncMock(return_value=agent)),
        SimpleNamespace(get_by_id=AsyncMock(return_value=draft)),
        SimpleNamespace(
            get_by_id=AsyncMock(
                return_value=SimpleNamespace(
                    project_id=project, status=CredentialStatus.active
                )
            )
        ),
        SimpleNamespace(validate=AsyncMock()),
        models=SimpleNamespace(get_by_id=AsyncMock(return_value=provider_model)),
        tools=SimpleNamespace(get_by_id=AsyncMock(return_value=tool)),
        allow_existing=changed in {"inactive_existing", "archived_existing"},
    )
    definition = SimpleNamespace(
        project_id=project, agent_id=agent_id, draft_id=draft_id, lifecycle="draft"
    )
    if changed not in {"ready", "inactive_existing"}:
        with pytest.raises(ConflictError):
            await case.execute(definition)
    else:
        result = await case.execute(definition)
        assert result["configuration_ready"] and result["execution_ready"]
