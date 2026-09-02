import pytest
from uuid import UUID

from modules.observability.application.dtos import (
    CreateTraceInput,
    CreateTraceOutput,
    CreateTraceEventInput,
    CreateTraceEventOutput,
    TraceSummaryResponse,
)
from modules.observability.application.interfaces.outbox import OutboxEventWriter
from modules.observability.application.interfaces.repositories import (
    TraceRepository,
    TraceEventRepository,
)
from modules.observability.application.use_cases import (
    CreateTraceUseCase,
    CreateTraceEventUseCase,
    GetTraceUseCase,
)
from modules.observability.domain.entities import TraceEvent
from modules.observability.domain.enums import TraceStatus, TraceEventType
from modules.observability.domain.errors import TraceNotFoundError
from tests.helpers import make_trace, fake_uuid


class TestCreateTraceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=TraceRepository)
        saved = make_trace()
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateTraceInput(
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            status="pending",
        )

        uc = CreateTraceUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateTraceOutput)
        assert result.trace_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_full_fields(self, mocker):
        mock_repo = mocker.AsyncMock(spec=TraceRepository)
        saved = make_trace()
        saved.status = TraceStatus.completed
        saved.total_latency_ms = 2000.0
        saved.provider = "openai"
        saved.model = "gpt-4"
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateTraceInput(
            project_id=saved.project_id,
            agent_id=saved.agent_id,
            status="completed",
            total_latency_ms=2000.0,
            provider="openai",
            model="gpt-4",
            fallback_used=True,
        )

        uc = CreateTraceUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert result.trace_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestCreateTraceEventUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=TraceEventRepository)
        saved = TraceEvent(
            trace_id=UUID(fake_uuid()),
            project_id=UUID(fake_uuid()),
            event_type=TraceEventType.llm_call,
        )
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateTraceEventInput(
            trace_id=saved.trace_id,
            project_id=saved.project_id,
            event_type="llm_call",
        )

        uc = CreateTraceEventUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateTraceEventOutput)
        assert result.event_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_with_cost_and_latency(self, mocker):
        mock_repo = mocker.AsyncMock(spec=TraceEventRepository)
        saved = TraceEvent(
            trace_id=UUID(fake_uuid()),
            project_id=UUID(fake_uuid()),
            event_type=TraceEventType.tool_call,
            latency_ms=300.0,
            cost_usd=0.01,
            payload={"tool": "web_search"},
        )
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)

        input_dto = CreateTraceEventInput(
            trace_id=saved.trace_id,
            project_id=saved.project_id,
            event_type="tool_call",
            latency_ms=300.0,
            cost_usd=0.01,
            payload={"tool": "web_search"},
        )

        uc = CreateTraceEventUseCase(repo=mock_repo, outbox=mock_outbox)
        result = await uc.execute(input_dto)

        assert result.event_id == saved.id
        mock_repo.save.assert_awaited_once()


class TestGetTraceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_trace_repo = mocker.AsyncMock(spec=TraceRepository)
        trace = make_trace()
        trace.status = TraceStatus.completed
        mock_trace_repo.get_by_id.return_value = trace

        mock_event_repo = mocker.AsyncMock(spec=TraceEventRepository)
        events = [
            TraceEvent(
                trace_id=trace.id,
                project_id=trace.project_id,
                event_type=TraceEventType.llm_call,
                latency_ms=500.0,
            )
        ]
        mock_event_repo.list_by_trace.return_value = events

        uc = GetTraceUseCase(trace_repo=mock_trace_repo, event_repo=mock_event_repo)
        result = await uc.execute(trace_id=trace.id)

        assert isinstance(result, TraceSummaryResponse)
        assert result.id == trace.id
        assert result.status == "completed"
        assert len(result.events) == 1
        assert result.events[0].event_type == "llm_call"
        mock_trace_repo.get_by_id.assert_awaited_once_with(trace.id)
        mock_event_repo.list_by_trace.assert_awaited_once_with(trace.id)

    @pytest.mark.asyncio
    async def test_trace_not_found(self, mocker):
        mock_trace_repo = mocker.AsyncMock(spec=TraceRepository)
        mock_trace_repo.get_by_id.return_value = None
        mock_event_repo = mocker.AsyncMock(spec=TraceEventRepository)

        uc = GetTraceUseCase(trace_repo=mock_trace_repo, event_repo=mock_event_repo)
        with pytest.raises(TraceNotFoundError, match="not found"):
            await uc.execute(trace_id=UUID(fake_uuid()))

        mock_trace_repo.get_by_id.assert_awaited_once()
        mock_event_repo.list_by_trace.assert_not_called()
