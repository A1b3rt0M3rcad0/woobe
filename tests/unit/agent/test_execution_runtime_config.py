from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.execution_runtime_config import (
    DEFAULT_INTERMEDIATE_MESSAGES_ENABLED,
    canonicalize_execution_runtime_config,
    intermediate_messages_enabled_from_runtime_config,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution.instrumented_primary_mixin import (
    InstrumentedPrimaryExecutionMixin,
)
from shared.contracts.errors import ValidationError


def test_historical_runtime_config_is_final_only() -> None:
    assert DEFAULT_INTERMEDIATE_MESSAGES_ENABLED is False
    assert intermediate_messages_enabled_from_runtime_config(None) is False
    assert intermediate_messages_enabled_from_runtime_config({}) is False
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution_strategy": "standard"}
    ) is False


def test_execution_runtime_config_reads_explicit_intermediate_policy() -> None:
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution": {"intermediate_messages": True}}
    ) is True
    assert intermediate_messages_enabled_from_runtime_config(
        {"execution": {"intermediate_messages": False}}
    ) is False


def test_execution_runtime_config_preserves_other_runtime_fields() -> None:
    raw = {
        "execution_strategy": "scientific_method",
        "execution": {
            "intermediate_messages": True,
            "future_setting": {"enabled": True},
        },
        "tools": {"tool_ids": []},
    }

    normalized = canonicalize_execution_runtime_config(raw)

    assert normalized == raw
    assert normalized is not raw
    assert normalized["execution"] is not raw["execution"]


@pytest.mark.parametrize(
    "value",
    [
        {"execution": "enabled"},
        {"execution": {"intermediate_messages": "yes"}},
        {"execution": {"intermediate_messages": 1}},
    ],
)
def test_execution_runtime_config_rejects_invalid_policy(value) -> None:
    with pytest.raises(ValidationError):
        canonicalize_execution_runtime_config(value)


class _PrepareHost(InstrumentedPrimaryExecutionMixin):
    pass


@pytest.mark.asyncio
@pytest.mark.parametrize("enabled", [False, True])
async def test_resolved_agent_runtime_config_binds_intermediate_policy_to_execution_context(
    enabled: bool,
) -> None:
    project_id = uuid4()
    agent_id = uuid4()
    session_id = uuid4()
    trace_id = uuid4()
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        settings={
            "runtime_config": {
                "execution": {"intermediate_messages": enabled},
            }
        },
    )
    session = SimpleNamespace(id=session_id)
    prepared = (
        agent,
        session,
        trace_id,
        None,
        None,
        {},
        None,
        None,
        None,
        None,
        [],
    )

    async def prepare_operation(_input):
        return prepared

    context = new_execution_context()
    token = current_execution.set(context)
    try:
        result = await _PrepareHost()._prepare_with_instrumentation(
            SimpleNamespace(project_id=project_id),
            prepare_operation,
        )
    finally:
        current_execution.reset(token)

    assert result is prepared
    assert context.intermediate_messages_enabled is enabled
    assert context.project_id == project_id
    assert context.agent_id == agent_id
    assert context.session_id == session_id
    assert context.trace_id == trace_id
