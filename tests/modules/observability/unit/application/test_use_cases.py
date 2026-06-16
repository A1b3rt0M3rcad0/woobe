from uuid import UUID

import pytest

from modules.observability.application.use_cases import (
    CreateTraceEventUseCase,
    CreateTraceUseCase,
    GetTraceUseCase,
    ListTracesUseCase,
)
from modules.observability.application.dtos import (
    CreateTraceEventInput,
    CreateTraceEventOutput,
    CreateTraceInput,
    CreateTraceOutput,
    ListTracesInput,
)
from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType
from modules.observability.domain.repositories import TraceEventRepository, TraceRepository
from shared.infra.errors import NotFoundError


class FakeTraceRepository(TraceRepository):
    def __init__(self):
        self._storage: dict[UUID, Trace] = {}

    async def save(self, trace: Trace) -> Trace:
        self._storage[trace.id] = trace
        return trace

    async def get_by_id(self, trace_id: UUID) -> Trace | None:
        return self._storage.get(trace_id)

    async def list_by_project(self, project_id: UUID, limit: int = 100, offset: int = 0) -> list[Trace]:
        return [t for t in self._storage.values() if t.project_id == project_id][offset:offset + limit]

    async def list_by_session(self, session_id: UUID, limit: int = 100, offset: int = 0) -> list[Trace]:
        return [t for t in self._storage.values() if t.session_id == session_id][offset:offset + limit]

    async def list_by_project_and_agent(self, project_id: UUID, agent_id: UUID, limit: int = 100, offset: int = 0) -> list[Trace]:
        return [t for t in self._storage.values() if t.project_id == project_id and t.agent_id == agent_id][offset:offset + limit]

    async def paginate_by_project(self, project_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def paginate_by_session(self, session_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def delete(self, trace_id: UUID) -> None:
        self._storage.pop(trace_id, None)


class FakeTraceEventRepository(TraceEventRepository):
    def __init__(self):
        self._storage: dict[UUID, TraceEvent] = {}

    async def save(self, event: TraceEvent) -> TraceEvent:
        self._storage[event.id] = event
        return event

    async def get_by_id(self, event_id: UUID) -> TraceEvent | None:
        return self._storage.get(event_id)

    async def list_by_trace(self, trace_id: UUID, limit: int = 100, offset: int = 0) -> list[TraceEvent]:
        return [e for e in self._storage.values() if e.trace_id == trace_id][offset:offset + limit]

    async def paginate_by_trace(self, trace_id: UUID, *, limit: int = 50, cursor: str | None = None):
        raise NotImplementedError

    async def delete(self, event_id: UUID) -> None:
        self._storage.pop(event_id, None)


class FakeOutboxWriter:
    def __init__(self):
        self.written = []

    async def write(self, aggregate_type: str, aggregate_id: UUID, event_type: str, payload: dict, **kwargs) -> None:
        self.written.append((aggregate_type, aggregate_id, event_type, payload))


class TestCreateTraceUseCase:
    @pytest.mark.asyncio
    async def test_create_trace_success(self):
        repo = FakeTraceRepository()
        outbox = FakeOutboxWriter()
        uc = CreateTraceUseCase(repo, outbox)

        pid = UUID("00000000-0000-0000-0000-000000000001")
        input_dto = CreateTraceInput(project_id=pid, provider="openai")
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateTraceOutput)
        assert isinstance(result.trace_id, UUID)

        saved = await repo.get_by_id(result.trace_id)
        assert saved is not None
        assert saved.project_id == pid
        assert saved.provider == "openai"

        assert len(outbox.written) == 1
        assert outbox.written[0][0] == "Trace"
        assert outbox.written[0][2] == "trace.created"


class TestCreateTraceEventUseCase:
    @pytest.mark.asyncio
    async def test_create_event_success(self):
        repo = FakeTraceEventRepository()
        outbox = FakeOutboxWriter()
        uc = CreateTraceEventUseCase(repo, outbox)

        tid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID("00000000-0000-0000-0000-000000000002")
        input_dto = CreateTraceEventInput(trace_id=tid, project_id=pid, event_type="llm_call")
        result = await uc.execute(input_dto)

        assert isinstance(result, CreateTraceEventOutput)
        assert isinstance(result.event_id, UUID)

        saved = await repo.get_by_id(result.event_id)
        assert saved is not None
        assert saved.trace_id == tid
        assert saved.event_type == TraceEventType.llm_call

        assert len(outbox.written) == 1
        assert outbox.written[0][0] == "TraceEvent"
        assert outbox.written[0][2] == "trace_event.created"


class TestGetTraceUseCase:
    @pytest.mark.asyncio
    async def test_get_existing_trace(self):
        trace_repo = FakeTraceRepository()
        event_repo = FakeTraceEventRepository()
        uc = GetTraceUseCase(trace_repo, event_repo)

        pid = UUID("00000000-0000-0000-0000-000000000001")
        trace = Trace(project_id=pid)
        saved = await trace_repo.save(trace)

        result = await uc.execute(saved.id)
        assert result.id == saved.id
        assert result.project_id == pid

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace_raises_error(self):
        trace_repo = FakeTraceRepository()
        event_repo = FakeTraceEventRepository()
        uc = GetTraceUseCase(trace_repo, event_repo)

        with pytest.raises(NotFoundError):
            await uc.execute(UUID("00000000-0000-0000-0000-000000000099"))


class TestListTracesUseCase:
    @pytest.mark.asyncio
    async def test_list_by_project(self):
        repo = FakeTraceRepository()
        uc = ListTracesUseCase(repo)

        pid = UUID("00000000-0000-0000-0000-000000000001")
        trace = Trace(project_id=pid)
        await repo.save(trace)

        input_dto = ListTracesInput(project_id=pid)
        results = await uc.execute(input_dto)
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_without_project_returns_empty(self):
        repo = FakeTraceRepository()
        uc = ListTracesUseCase(repo)

        input_dto = ListTracesInput()
        results = await uc.execute(input_dto)
        assert results == []
