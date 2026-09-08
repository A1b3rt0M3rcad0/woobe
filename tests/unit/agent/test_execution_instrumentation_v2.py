import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain_core.messages import SystemMessage

from modules.agent.infra.execution.execution_instrumentation import (
    aggregate_usage,
    resolve_effective_output_tokens,
)
from modules.agent.infra.execution.instrumented_execution_runner import (
    run_instrumented_execution,
)


class Result:
    def __init__(self, content, tool_calls=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage_metadata = usage or {}
        self.response_metadata = {}


def _agent():
    return SimpleNamespace(
        provider=SimpleNamespace(value="custom"),
        model="model",
        temperature=0.2,
        max_output_tokens=100,
        settings={},
    )


async def _execute_sum(_call, _tool_id):
    return {"success": True, "duration_ms": 10, "output": {"result": 1}}


def test_effective_output_tokens_clamps_to_invoked_model_capability():
    assert resolve_effective_output_tokens(8192, {"max_output_tokens": 4096}) == 4096
    assert resolve_effective_output_tokens(2048, {"max_output_tokens": 4096}) == 2048
    assert resolve_effective_output_tokens(2048, {}) == 2048


@pytest.mark.asyncio
async def test_primary_model_factory_uses_effective_output_capability():
    agent = _agent()
    agent.settings = {"model_pricing": {"max_output_tokens": 40}}
    model = MagicMock()
    model.ainvoke = AsyncMock(
        return_value=Result(
            "ok",
            usage={"input_tokens": 2, "output_tokens": 1, "total_tokens": 3},
        )
    )
    factory = MagicMock()
    factory.create_chat_model.return_value = model

    await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=_execute_sum,
        clean_json_answer=lambda value: value,
        agent=agent,
        api_key="key",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=False,
        agent_tools=[],
        tool_name_to_id={},
        messages=[],
    )

    assert factory.create_chat_model.call_args.kwargs["max_tokens"] == 40


@pytest.mark.asyncio
async def test_parallel_tools_and_no_redundant_json_repair():
    tool_request = Result(
        "",
        [
            {"id": "a", "name": "sum", "args": {"a": 8, "b": 8}},
            {"id": "b", "name": "sum", "args": {"a": 9, "b": 8}},
        ],
        {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
    )
    structured_followup = Result(
        '{"message":"ok"}',
        usage={"input_tokens": 20, "output_tokens": 4, "total_tokens": 24},
    )
    tool_model = MagicMock()
    tool_model.bind_tools.return_value = tool_model
    tool_model.ainvoke = AsyncMock(side_effect=[tool_request, structured_followup])
    factory = MagicMock()
    factory.create_chat_model.side_effect = [tool_model]

    active = 0
    peak = 0

    async def execute(call, tool_id):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return await _execute_sum(call, tool_id)

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=execute,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="key",
        base_url=None,
        response_format={"schema": {"type": "object"}},
        json_enabled=True,
        has_tools=True,
        agent_tools=[{"type": "function"}],
        tool_name_to_id={"sum": "id"},
        messages=[],
    )

    assert peak == 2
    assert factory.create_chat_model.call_count == 1
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
    ]
    initial_messages = tool_model.ainvoke.await_args_list[0].args[0]
    assert isinstance(initial_messages[0], SystemMessage)
    assert "complete and authoritative" in initial_messages[0].content
    assert "return only valid JSON" in initial_messages[0].content
    usage, complete, cost_status = aggregate_usage(execution.llm_calls)
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (30, 6, 36)
    assert complete is True
    assert usage.cost_usd is None
    assert cost_status == "unknown_pricing"


@pytest.mark.asyncio
async def test_invalid_tool_followup_uses_one_json_repair_model():
    tool_request = Result(
        "",
        [{"id": "a", "name": "sum", "args": {"a": 8, "b": 8}}],
        {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
    )
    invalid_followup = Result(
        "The result is 16.",
        usage={"input_tokens": 5, "output_tokens": 1, "total_tokens": 6},
    )
    repaired = Result(
        '{"message":"16"}',
        usage={"input_tokens": 20, "output_tokens": 4, "total_tokens": 24},
    )
    tool_model = MagicMock()
    tool_model.bind_tools.return_value = tool_model
    tool_model.ainvoke = AsyncMock(side_effect=[tool_request, invalid_followup])
    repair_model = MagicMock()
    repair_model.ainvoke = AsyncMock(return_value=repaired)
    factory = MagicMock()
    factory.create_chat_model.side_effect = [tool_model, repair_model]

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=_execute_sum,
        clean_json_answer=lambda value: value,
        agent=_agent(),
        api_key="key",
        base_url=None,
        response_format={"schema": {"type": "object"}},
        json_enabled=True,
        has_tools=True,
        agent_tools=[{"type": "function"}],
        tool_name_to_id={"sum": "id"},
        messages=[],
    )

    assert execution.result is repaired
    assert factory.create_chat_model.call_count == 2
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
        "json_repair",
    ]
