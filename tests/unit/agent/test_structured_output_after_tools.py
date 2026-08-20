from unittest.mock import AsyncMock, MagicMock

import pytest

from modules.agent.runtime.structured_output_ask_use_case import (
    StructuredOutputAskAgentUseCase,
)


@pytest.mark.asyncio
async def test_json_formatting_result_replaces_text_result_after_tool_call():
    tool_request = MagicMock()
    tool_request.content = ""
    tool_request.tool_calls = [
        {
            "id": "call-1",
            "name": "sum_two_numbers",
            "args": {"a": "8", "b": "8"},
        }
    ]

    text_result = MagicMock()
    text_result.content = "The result is 16."
    text_result.tool_calls = []

    json_result = MagicMock()
    json_result.content = '{"message":"16"}'
    json_result.tool_calls = []

    tool_model = MagicMock()
    tool_model.bind_tools.return_value = tool_model
    tool_model.ainvoke = AsyncMock(
        side_effect=[tool_request, text_result],
    )

    json_model = MagicMock()
    json_model.ainvoke = AsyncMock(return_value=json_result)

    llm_factory = MagicMock()
    llm_factory.create_chat_model.side_effect = [tool_model, json_model]

    use_case = StructuredOutputAskAgentUseCase(
        session_factory=MagicMock(),
        llm_factory=llm_factory,
    )
    use_case._execute_single_tool = AsyncMock(
        return_value={"success": True, "output": {"result": "16"}}
    )

    agent = MagicMock()
    agent.provider.value = "custom"
    agent.model = "deepseek-v4-flash"
    agent.temperature = 0.2
    agent.max_output_tokens = 1000

    result, tool_calls, tool_was_called, json_latency = (
        await use_case._execute_llm(
            agent=agent,
            api_key="secret",
            base_url="https://provider.example/v1",
            response_format={
                "enabled": True,
                "type": "json",
                "schema": {"message": "string"},
            },
            json_enabled=True,
            has_tools=True,
            agent_tools=[{"type": "function"}],
            tool_name_to_id={"sum_two_numbers": "tool-id"},
            messages=[],
        )
    )

    assert result is json_result
    assert result.content == '{"message":"16"}'
    assert tool_was_called is True
    assert len(tool_calls) == 1
    assert json_latency is None
    json_model.ainvoke.assert_awaited_once()
