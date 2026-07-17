from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

from modules.agent.application.use_cases.instrumented_execution_runner import (
    run_instrumented_execution,
)


class SequenceToolModel:
    def __init__(self) -> None:
        self.responses = [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "sum",
                        "args": {"a": 8, "b": 8},
                        "id": "call-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="16"),
        ]
        self.invocation_count = 0

    def bind_tools(self, _tools, *, tool_choice):
        assert tool_choice == "auto"
        return self

    async def ainvoke(self, _messages):
        response = self.responses[self.invocation_count]
        self.invocation_count += 1
        return response


class RecordingLlmFactory:
    def __init__(self, model: SequenceToolModel) -> None:
        self.model = model
        self.create_count = 0

    def create_chat_model(self, **_kwargs):
        self.create_count += 1
        return self.model


@pytest.mark.asyncio
async def test_text_tool_execution_uses_followup_as_final_response() -> None:
    model = SequenceToolModel()
    factory = RecordingLlmFactory(model)
    agent = SimpleNamespace(
        provider="openrouter",
        model="deepseek/deepseek-v4-flash",
        temperature=0.2,
        max_output_tokens=1000,
        settings={},
    )

    async def execute_single_tool(_tool_call, resolved_tool_id):
        assert resolved_tool_id == "tool-id"
        return {
            "success": True,
            "output": {
                "body": {"result": "16", "error": None},
                "status_code": 200,
            },
            "duration_ms": 1,
            "error": None,
        }

    execution = await run_instrumented_execution(
        llm_factory=factory,
        execute_single_tool=execute_single_tool,
        clean_json_answer=lambda value: value,
        agent=agent,
        api_key="test-key",
        base_url=None,
        response_format={},
        json_enabled=False,
        has_tools=True,
        agent_tools=[
            {
                "type": "function",
                "function": {
                    "name": "sum",
                    "description": "Sum two integers",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "a": {"type": "integer"},
                            "b": {"type": "integer"},
                        },
                        "required": ["a", "b"],
                    },
                },
            }
        ],
        tool_name_to_id={"sum": "tool-id"},
        messages=[],
    )

    assert factory.create_count == 1
    assert model.invocation_count == 2
    assert [call["phase"] for call in execution.llm_calls] == [
        "tool_planning",
        "tool_followup_1",
    ]
    assert execution.result.content == "16"
    assert len(execution.tool_calls) == 1
    assert execution.tool_calls[0].success is True
