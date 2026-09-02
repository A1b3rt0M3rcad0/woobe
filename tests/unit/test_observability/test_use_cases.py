import pytest
from uuid import UUID

from modules.observability.application.dtos import (
    CreateTraceEventInput,
    CreateTraceEventOutput,
    CreateTraceInput,
    CreateTraceOutput,
    TraceSummaryResponse,
)
from modules.observability.application.interfaces.outbox import OutboxEventWriter
from modules.observability.application.interfaces.repositories import (
    TraceEventRepository,
    TraceRepository,
)
from modules.observability.application.use_cases import (
    CreateTraceEventUseCase,
    CreateTraceUseCase,
    GetTraceUseCase,
)
from modules.observability.domain.entities import TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.domain.errors import TraceNotFoundError
from tests.helpers import fake_uuid, make_trace


class TestCreateTraceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        mock_repo = mocker.AsyncMock(spec=TraceRepository)
        saved = make_trace()
        mock_repo.save.return_value = saved
        mock_outbox = mocker.AsyncMock(spec=OutboxEventWriter)
        result = await CreateTraceUseCase(mock_repo, mock_outbox).execute(
            CreateTraceInput(project_id=saved.project_id, agent_id=saved.agent_id)
        )
        assert isinstance(result, CreateTraceOutput)
        assert result.trace_id == saved.id
        mock_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()


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
        result = await CreateTraceEventUseCase(mock_repo, mock_outbox).execute(
            CreateTraceEventInput(
                trace_id=saved.trace_id,
                project_id=saved.project_id,
                event_type="llm_call",
            )
        )
        assert isinstance(result, CreateTraceEventOutput)
        assert result.event_id == saved.id
        mock_outbox.write.assert_awaited_once()


class TestGetTraceUseCase:
    @pytest.mark.asyncio
    async def test_success(self, mocker):
        trace_repo = mocker.AsyncMock(spec=TraceRepository)
        trace = make_trace()
        trace.status = TraceStatus.completed
        trace_repo.get_by_id.return_value = trace
        event_repo = mocker.AsyncMock(spec=TraceEventRepository)
        event_repo.list_by_trace.return_value = []
        result = await GetTraceUseCase(trace_repo, event_repo).execute(trace.id)
        assert isinstance(result, TraceSummaryResponse)
        assert result.id == trace.id

    @pytest.mark.asyncio
    async def test_trace_not_found(self, mocker):
        trace_repo = mocker.AsyncMock(spec=TraceRepository)
        trace_repo.get_by_id.return_value = None
        event_repo = mocker.AsyncMock(spec=TraceEventRepository)
        with pytest.raises(TraceNotFoundError, match="not found"):
            await GetTraceUseCase(trace_repo, event_repo).execute(UUID(fake_uuid()))
        event_repo.list_by_trace.assert_not_called()
