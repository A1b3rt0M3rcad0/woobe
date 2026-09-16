from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.interfaces.execution_strategy import ExecutionStrategyRequest
from modules.agent.infra.execution.strategies.standard import (
    build_standard_strategy_definition,
)
from modules.agent.infra.execution.strategy_runtime.runner import (
    execute_strategy_definition,
)


class _SequenceModel:
    def __init__(self) -> None:
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-1",
                        "name": "lookup",
                        "args": {"id": "a"},
                        "type": "tool_call",
                    },
                    {
                        "id": "call-2",
                        "name": "lookup",
                        "args": {"id": "b"},
                        "type": "tool_call",
                    },
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "call-3",
                        "name": "lookup",
                        "args": {"id": "c"},
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="combined answer"),
        ]
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        result = self.responses[self.invocation_count]
        self.invocation_count += 1
        return result


class _Factory:
    def __init__(self, model) -> None:
        self.model = model

    def create_chat_model(self, **_kwargs):
        return self.model


@pytest.mark.asyncio
async def test_standard_strategy_supports_multiple_parallel_tools_and_followup_rounds() -> None:
    model = _SequenceModel()
    executed: list[str] = []

    async def execute_single_tool(tool_call, resolved_tool_id):
        assert resolved_tool_id == "tool-id"
        executed.append(tool_call["id"])
        return {
            "success": True,
            "output": {"result": tool_call["args"]["id"]},
            "duration_ms": 1,
            "error": None,
        }

    request = ExecutionStrategyRequest(
        llm_factory=_Factory(model),
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=SimpleNamespace(
            provider="openai",
            model="test-model",
            temperature=0.2,
            max_output_tokens=512,
            settings={},
        ),  # type: ignore[arg-type]
        api_key="secret",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=[
            {
                "type": "function",
                "function": {
                    "name": "lookup",
                    "description": "Lookup",
                    "parameters": {"type": "object"},
                },
            }
        ],
        tool_name_to_id={"lookup": "tool-id"},
        messages=[],
        context_assembler=None,
    )

    execution = await execute_strategy_definition(
        build_standard_strategy_definition(),
        request,
    )

    assert model.invocation_count == 3
    assert sorted(executed[:2]) == ["call-1", "call-2"]
    assert executed[2:] == ["call-3"]
    assert execution.result.content == "combined answer"
    assert len(execution.tool_calls) == 3
    assert [call["phase"] for call in execution.llm_calls] == [
        "capability_response_generation",
        "tool_followup_1",
        "tool_followup_2",
    ]
