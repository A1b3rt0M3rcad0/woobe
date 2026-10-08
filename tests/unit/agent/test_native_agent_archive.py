from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.ai_dtos import UpdateAgentInput
from modules.agent.infra.adapters import legacy_runtime_status_adapter as module


@pytest.mark.asyncio
async def test_archive_reaches_owner_guards_and_disables_runtime_environments(monkeypatch):
    agent_id, project_id = uuid4(), uuid4()
    result = SimpleNamespace(project_id=project_id, status="archived")
    delegate = SimpleNamespace(execute=AsyncMock(return_value=result))
    session = object()
    runtime = AsyncMock()
    monkeypatch.setattr(module, "set_runtime_environment_enabled", runtime)
    adapter = module.LegacyRuntimeStatusUpdateAdapter(delegate, SimpleNamespace(session=session))
    assert await adapter.execute(agent_id, UpdateAgentInput(status="archived")) is result
    assert delegate.execute.await_args.args[1].status.value == "archived"
    assert runtime.await_count == len(module.RUNTIME_ENVIRONMENTS)
    assert all(call.kwargs["enabled"] is False for call in runtime.await_args_list)


@pytest.mark.asyncio
async def test_rejected_archive_does_not_disable_runtime(monkeypatch):
    runtime = AsyncMock()
    monkeypatch.setattr(module, "set_runtime_environment_enabled", runtime)
    delegate = SimpleNamespace(execute=AsyncMock(side_effect=PermissionError("dependency guard")))
    adapter = module.LegacyRuntimeStatusUpdateAdapter(delegate, SimpleNamespace(session=object()))
    with pytest.raises(PermissionError):
        await adapter.execute(uuid4(), UpdateAgentInput(status="archived"))
    runtime.assert_not_awaited()
