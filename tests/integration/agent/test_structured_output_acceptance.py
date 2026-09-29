from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.structured_json_repair import (
    repair_json_if_needed,
)


class RepairModel:
    def __init__(self, content: str = "", failure: Exception | None = None):
        self.content = content
        self.failure = failure

    async def ainvoke(self, _messages):
        if self.failure is not None:
            raise self.failure
        result = AIMessage(content=self.content)
        result.usage_metadata = {
            "input_tokens": 4,
            "output_tokens": 3,
            "total_tokens": 7,
        }
        return result


class RepairFactory:
    def __init__(self, model):
        self.model = model
        self.calls = []

    def create_chat_model(self, **kwargs):
        self.calls.append(kwargs)
        return self.model


def _arguments(factory, execution):
    return {
        "execution": execution,
        "call_index": 1,
        "llm_factory": factory,
        "provider": "compatible-provider",
        "model_name": "model-test",
        "api_key": "credential-placeholder",
        "base_url": None,
        "max_tokens": 128,
        "schema": {"type": "object"},
        "clean_json_answer": lambda value: value,
        "context_capability": ContextAssemblyCapability(
            assembler=None,
            provider="compatible-provider",
            model_name="model-test",
            pricing_snapshot=None,
        ),
    }


@pytest.mark.asyncio
async def test_valid_json_skips_repair() -> None:
    factory = RepairFactory(RepairModel('{"ok": true}'))
    execution = InstrumentedExecution(result=AIMessage(content='{"ok": true}'))

    result = await repair_json_if_needed(**_arguments(factory, execution))

    assert result is execution
    assert factory.calls == []
    assert result.llm_calls == []


@pytest.mark.asyncio
async def test_invalid_json_is_repaired_and_instrumented() -> None:
    factory = RepairFactory(RepairModel('{"ok": true}'))
    execution = InstrumentedExecution(result=AIMessage(content="not-json"))

    result = await repair_json_if_needed(**_arguments(factory, execution))

    assert result.result.content == '{"ok": true}'
    assert len(factory.calls) == 1
    assert factory.calls[0]["response_format"] == {"type": "json_object"}
    assert result.llm_calls[-1]["phase"] == "json_repair"
    assert result.llm_calls[-1]["status"] == "success"
    assert result.timeline[-1]["kind"] == "llm"


@pytest.mark.asyncio
async def test_failed_json_repair_records_failed_call() -> None:
    factory = RepairFactory(RepairModel(failure=ValueError("invalid repair output")))
    execution = InstrumentedExecution(result=AIMessage(content="not-json"))

    with pytest.raises(InstrumentedExecutionError) as exc_info:
        await repair_json_if_needed(**_arguments(factory, execution))

    assert exc_info.value.llm_calls[-1]["phase"] == "json_repair"
    assert exc_info.value.llm_calls[-1]["status"] == "error"
    assert exc_info.value.timeline[-1]["kind"] == "llm"
