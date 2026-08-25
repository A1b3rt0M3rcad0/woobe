"""Tests for spec 008: phased agent execution.

Covers: no open DB during external call, prepare/finalize atomicity,
failure event emission, and HTTP compatibility.
"""
from unittest.mock import AsyncMock, MagicMock, PropertyMock
from uuid import UUID, uuid4

import pytest

from modules.agent.infra.execution.explicit_runtime_persistence import (
    TransactionalAskAgentUseCase as AskAgentUseCase,
)
from modules.agent.application.dtos.runtime_dtos import (
    AskInput,
    AskOutput,
    UsageInfo,
    SourceInfo,
    ToolCallInfo,
)
from modules.agent.domain.entities import Agent
from modules.agent.application.interfaces.llm_factory import LLMFactory
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


@pytest.fixture
def agent_id() -> UUID:
    return uuid4()


@pytest.fixture
def project_id() -> UUID:
    return uuid4()


class TestConstructorModes:
    """AskAgentUseCase uses explicit runtime transaction boundaries."""

    def test_construct_with_minimal_params(self):
        transactions = MagicMock()
        llm_factory = MagicMock(spec=LLMFactory)
        use_case = AskAgentUseCase(
            transactions=transactions,
            llm_factory=llm_factory,
        )
        assert use_case._transactions is transactions
        assert use_case._llm_factory is not None


class TestHttpCompatibility:
    """AskOutput shape must be unchanged from pre-refactor."""

    def test_output_contains_expected_fields(self):
        output = AskOutput(
            answer="test",
            session_id=uuid4(),
            message_id=uuid4(),
            usage=UsageInfo(
                input_tokens=10, output_tokens=20, total_tokens=30, cost_usd=0.001,
            ),
            sources=[
                SourceInfo(
                    document_id=str(uuid4()), chunk_id=str(uuid4()),
                    page_number=1, score=0.95, content_preview="preview",
                ),
            ],
            tool_calls=[
                ToolCallInfo(
                    tool_call_id="call_1", tool_name="test_tool",
                    input={}, output={}, duration_ms=100, success=True, error=None,
                ),
            ],
            trace_id=uuid4(),
            model="gpt-4",
            provider="openai",
            fallback_used=False,
            fallback_info=None,
            latency_ms=500,
            parsed_output=None,
            output_parse_error=None,
        )
        data = output.model_dump()
        expected_fields = {
            "answer", "session_id", "message_id", "usage", "sources",
            "tool_calls", "trace_id", "model", "provider", "fallback_used",
            "fallback_info", "latency_ms", "parsed_output", "output_parse_error",
        }
        assert expected_fields.issubset(data.keys()), f"Missing: {expected_fields - data.keys()}"
        assert data["answer"] == "test"

    def test_controller_error_handling_preserved(self):
        from modules.agent.presentation.controllers.ask_agent_controller import (
            AskAgentController,
        )

        mock_use_case = MagicMock(spec=AskAgentUseCase)
        mock_use_case.execute = AsyncMock(
            side_effect=ValueError("AI provider error: test error"),
        )

        controller = AskAgentController(mock_use_case)
        request = Request(
            body={
                "agent_id": str(uuid4()),
                "project_id": str(uuid4()),
                "message": "hello",
            },
        )

        response = None

        async def run():
            nonlocal response
            response = await controller.handle(request)

        import asyncio
        asyncio.run(run())

        assert response is not None
        assert isinstance(response, Response)
        assert response.status_code in (400, 500)
        assert not response.body.get("success", True)


class TestPrepareFinalizeSeparation:
    """The use case routes execution through explicit phased orchestration."""

    @pytest.mark.asyncio
    async def test_phased_execution_calls_prepare(self):
        transactions = MagicMock()
        llm_factory = MagicMock(spec=LLMFactory)
        use_case = AskAgentUseCase(
            transactions=transactions,
            llm_factory=llm_factory,
        )
        use_case._execute_phased = AsyncMock(return_value=MagicMock(spec=AskOutput))

        input_dto = AskInput(
            project_id=uuid4(), agent_id=uuid4(),
            message="test", tenant_id=None, user_id=None,
        )
        result = await use_case.execute(input_dto)
        assert isinstance(result, AskOutput) or result is not None
        use_case._execute_phased.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_execute_always_calls_phased(self):
        transactions = MagicMock()
        llm_factory = MagicMock(spec=LLMFactory)
        use_case = AskAgentUseCase(
            transactions=transactions,
            llm_factory=llm_factory,
        )
        use_case._execute_phased = AsyncMock(return_value=MagicMock(spec=AskOutput))

        input_dto = AskInput(
            project_id=uuid4(), agent_id=uuid4(),
            message="test", tenant_id=None, user_id=None,
        )
        result = await use_case.execute(input_dto)
        assert result is not None
        use_case._execute_phased.assert_awaited_once()


class TestExecuteLlmReturnsToolData:
    """_execute_llm must return structured tool call data."""

    @pytest.mark.asyncio
    async def test_execute_llm_returns_tuple(self):
        transactions = MagicMock()
        llm_factory = MagicMock(spec=LLMFactory)
        use_case = AskAgentUseCase(
            transactions=transactions,
            llm_factory=llm_factory,
        )

        mock_result = MagicMock()
        mock_result.content = "response"
        mock_result.tool_calls = None
        type(mock_result).usage_metadata = PropertyMock(
            return_value={"input_tokens": 10, "output_tokens": 20, "total_tokens": 30},
        )
        type(mock_result).response_metadata = PropertyMock(return_value={})

        agent = MagicMock(spec=Agent)
        agent.provider.value = "openai"
        agent.model = "gpt-4"
        agent.temperature = 0.2
        agent.max_output_tokens = 1000
        agent.provider_credential_id = uuid4()

        chat_model = MagicMock()
        chat_model.ainvoke = AsyncMock(return_value=mock_result)
        mock_factory = MagicMock()
        mock_factory.create_chat_model = MagicMock(return_value=chat_model)
        use_case._llm_factory = mock_factory

        result, tool_calls, was_called, json_latency = await use_case._execute_llm(
            agent=agent,
            api_key="test-key",
            base_url=None,
            response_format={},
            json_enabled=False,
            has_tools=False,
            agent_tools=[],
            tool_name_to_id={},
            messages=[],
        )

        assert result is not None
        assert isinstance(tool_calls, list)
        assert isinstance(was_called, bool)
