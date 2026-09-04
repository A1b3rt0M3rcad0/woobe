from __future__ import annotations

from types import SimpleNamespace

import pytest

from modules.agent.infra.execution.instrumented_fallback_mixin import (
    InstrumentedFallbackMixin,
)
from modules.agent.infra.execution.runtime_streaming import (
    RuntimeStreamChannel,
    current_runtime_stream,
)


class _Factory:
    def __init__(self) -> None:
        self.kwargs = None
        self.model = object()

    def create_chat_model(self, **kwargs):
        self.kwargs = kwargs
        return self.model


class _Runtime(InstrumentedFallbackMixin):
    def __init__(self, factory: _Factory, context_assembler=None) -> None:
        self._llm_factory = factory
        self._context_assembler = context_assembler


@pytest.mark.asyncio
async def test_fallback_uses_streaming_model_and_public_final_phase(monkeypatch) -> None:
    factory = _Factory()
    context_assembler = object()
    runtime = _Runtime(factory, context_assembler)
    captured = {}

    async def fake_invoke_llm(**kwargs):
        captured.update(kwargs)
        return (
            SimpleNamespace(content="fallback answer", usage_metadata={}),
            {
                "call_id": "fallback-call",
                "call_index": 1,
                "phase": kwargs["phase"],
                "status": "success",
                "occurred_at": "2026-08-28T00:00:00+00:00",
                "input_tokens": 10,
                "output_tokens": 4,
                "total_tokens": 14,
                "usage_complete": True,
                "cost_usd": 0.0,
                "cost_status": "known",
            },
        )

    monkeypatch.setattr(
        "modules.agent.infra.execution.instrumented_fallback_mixin.invoke_llm",
        fake_invoke_llm,
    )

    agent = SimpleNamespace(
        provider="custom",
        model="primary-model",
        fallback_provider="custom",
        fallback_model="fallback-model",
        fallback_credential_id=None,
        fallback_provider_model_id=None,
        temperature=0.2,
        max_output_tokens=256,
        settings={},
    )
    channel = RuntimeStreamChannel()
    stream_token = current_runtime_stream.set(channel)
    try:
        result, provider, _latency, info = await runtime._try_fallback(
            agent,
            [],
            False,
            "primary failed",
        )
    finally:
        current_runtime_stream.reset(stream_token)

    assert result.content == "fallback answer"
    assert provider == "custom"
    assert info["fallback_model"] == "fallback-model"
    assert factory.kwargs is not None
    assert factory.kwargs["streaming"] is True
    assert captured["phase"] == "final_response_generation"
    assert captured["model"] is factory.model
    assert captured["context_assembler"] is context_assembler
