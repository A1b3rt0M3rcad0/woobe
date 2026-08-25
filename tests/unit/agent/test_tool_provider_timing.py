import asyncio

import pytest

from modules.agent.infra.execution.execution_instrumentation import execute_tool_call
from modules.agent.infra.execution.tool_invocation_metrics import (
    current_tool_invocation_metrics,
    record_tool_provider_latency,
)


def test_provider_timing_is_not_recorded_without_an_instrumented_invocation() -> None:
    record_tool_provider_latency(90)
    assert current_tool_invocation_metrics.get() is None


@pytest.mark.asyncio
async def test_provider_timing_is_captured_without_leaking_into_tool_output() -> None:
    async def execute(_tool_call: dict, _resolved_tool_id: str) -> dict:
        record_tool_provider_latency(90)
        return {
            "success": True,
            "output": {"duration_ms": 10, "customer": "active"},
            "duration_ms": 100,
            "error": None,
        }

    info, _message, payload = await execute_tool_call(
        execute=execute,
        tool_call={"id": "call-1", "name": "customer_lookup", "args": {}},
        resolved_tool_id="tool-1",
    )

    assert payload["provider_latency_ms"] == 90
    assert "provider_latency_ms" not in info.output
    assert info.output == {
        "success": True,
        "output": {"duration_ms": 10, "customer": "active"},
        "duration_ms": 100,
        "error": None,
    }


@pytest.mark.asyncio
async def test_parallel_tool_provider_timings_are_task_local() -> None:
    async def execute(_tool_call: dict, resolved_tool_id: str) -> dict:
        if resolved_tool_id == "tool-a":
            await asyncio.sleep(0.01)
            record_tool_provider_latency(12)
        else:
            record_tool_provider_latency(37)
            await asyncio.sleep(0.02)
        return {
            "success": True,
            "output": {"tool": resolved_tool_id},
            "duration_ms": 50,
            "error": None,
        }

    first, second = await asyncio.gather(
        execute_tool_call(
            execute=execute,
            tool_call={"id": "call-a", "name": "tool_a", "args": {}},
            resolved_tool_id="tool-a",
        ),
        execute_tool_call(
            execute=execute,
            tool_call={"id": "call-b", "name": "tool_b", "args": {}},
            resolved_tool_id="tool-b",
        ),
    )

    assert first[2]["provider_latency_ms"] == 12
    assert second[2]["provider_latency_ms"] == 37
    assert current_tool_invocation_metrics.get() is None
