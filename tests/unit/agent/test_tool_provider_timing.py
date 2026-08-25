from modules.agent.infra.execution.execution_instrumentation import (
    tool_provider_latency_ms,
)


def test_tool_provider_latency_ignores_arbitrary_duration_fields() -> None:
    assert tool_provider_latency_ms({"duration_ms": 10}) is None
    assert tool_provider_latency_ms({"output": {"duration_ms": 20}}) is None


def test_tool_provider_latency_requires_explicit_adapter_measurement() -> None:
    assert tool_provider_latency_ms({"provider_latency_ms": 90}) == 90
    assert tool_provider_latency_ms({"provider_latency_ms": 16.5}) == 16.5
