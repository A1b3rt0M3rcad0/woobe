from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.tool_release_snapshots import (
    tool_to_release_snapshot,
)
from modules.agent.infra.execution.agent_tool_runtime_gateway import (
    AgentToolRuntimeGateway,
)
from modules.agent.infra.execution.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)


# Existing test helpers and tests above remain unchanged in the repository.
# This replacement only updates the release-tool snapshot test contract.


@pytest.mark.asyncio
async def test_streaming_executes_release_tool_snapshot(monkeypatch):
    tool = _tool()
    snapshot = tool_to_release_snapshot(tool)
    context = new_execution_context()
    context.tool_snapshots = {str(tool.id): snapshot}
    token = current_execution.set(context)

    result = SimpleNamespace(success=True, output={"ok": True}, duration_ms=3, error=None)
    registry = SimpleNamespace(execute=AsyncMock(return_value=result))
    transactions = SimpleNamespace(
        run=AsyncMock(
            side_effect=AssertionError("release snapshot must not read from DB")
        )
    )

    monkeypatch.setattr(
        "modules.agent.infra.execution.agent_tool_runtime_gateway.build_tool_runtime_registry",
        lambda **_kwargs: registry,
    )

    gateway = AgentToolRuntimeGateway(
        transactions,
        SimpleNamespace(encryption_key="test-encryption-key"),
        object(),
    )
    try:
        output = await gateway.execute_tool(tool.id, {})
    finally:
        current_execution.reset(token)

    executed_tool = registry.execute.await_args.args[0]
    assert executed_tool.config == tool.config
    assert output["success"] is True
    transactions.run.assert_not_awaited()
