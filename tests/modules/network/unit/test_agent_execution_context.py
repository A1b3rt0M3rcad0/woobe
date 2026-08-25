from __future__ import annotations

import asyncio
from types import SimpleNamespace

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.composition.runtime.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)


class _ExecutionParent:
    async def execute(self, _input_dto):
        return current_execution.get()


class _ExecutionSubject(InstrumentedPrimaryExecutionMixin, _ExecutionParent):
    pass


def test_caller_owned_network_context_is_preserved_for_agent_execution() -> None:
    seeded = new_execution_context()
    seeded.internal_tool_definitions = [
        {
            "type": "function",
            "function": {"name": "delegate_to_specialist"},
        }
    ]
    seeded.internal_tool_name_to_id = {"delegate_to_specialist": "tool-id"}
    token = current_execution.set(seeded)
    try:
        observed = asyncio.run(
            _ExecutionSubject().execute(SimpleNamespace(metadata={}))
        )
        assert observed is seeded
        assert observed.internal_tool_definitions == seeded.internal_tool_definitions
        assert current_execution.get() is seeded
    finally:
        current_execution.reset(token)


def test_standalone_agent_execution_still_owns_and_resets_its_context() -> None:
    assert current_execution.get() is None

    observed = asyncio.run(
        _ExecutionSubject().execute(
            SimpleNamespace(metadata={"client_sent_at": "2026-07-14T00:00:00Z"})
        )
    )

    assert observed is not None
    assert observed.client_sent_at == "2026-07-14T00:00:00Z"
    assert current_execution.get() is None
