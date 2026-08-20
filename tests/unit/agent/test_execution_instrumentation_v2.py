import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.agent.runtime.execution_instrumentation import aggregate_usage
from modules.agent.runtime.instrumented_execution_runner import run_instrumented_execution


class Result:
    def __init__(self, content, tool_calls=None, usage=None):
        self.content = content
        self.tool_calls = tool_calls or []
        self.usage_metadata = usage or {}
        self.response_metadata = {}


@pytest.mark.asyncio
async def test_parallel_tools_and_no_redundant_json_repair():
    planning = Result("", [
        {"id": "a", "name": "sum", "args": {"a": 8, "b": 8}},
        {"id": "b", "name": "sum", "args": {"a": 9, "b": 8}},
    ], {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12})
    decision = Result("", usage={
        "input_tokens": 5, "output_tokens": 1, "total_tokens": 6,
    })
    final = Result('{"message":"ok"}', usage={
        "input_tokens": 20, "output_tokens": 4, "total_tokens": 24,
    })
    tool_model = MagicMock()
    tool_model.bind_tools.return_value = tool_model
    tool_model.ainvoke = AsyncMock(side_effect=[planning, decision])
    final_model = MagicMock()
    final_model.ainvoke = AsyncMock(return_value=final)
    factory = MagicMock()
    factory.create_chat_model.side_effect = [tool_model, final_model]

    active = 0
    peak = 0

    async def execute(call, _tool_id):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.01)
        active -= 1
        return {"success": True, "duration_ms": 10, "output": {"result": 1}}

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=execute,
        clean_json_answer=lambda value: value,
        agent=MagicMock(provider=MagicMock(value="custom"), model="model", temperature=0.2, max_output_tokens=100),
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
    assert len(execution.llm_calls) == 3
    assert all(call["phase"] != "json_repair" for call in execution.llm_calls)
    usage, complete, cost_status = aggregate_usage(execution.llm_calls)
    assert (usage.input_tokens, usage.output_tokens, usage.total_tokens) == (35, 7, 42)
    assert complete is True
    assert usage.cost_usd is None
    assert cost_status == "unknown_pricing"
