from uuid import UUID

import pytest

from modules.observability.application.dtos import (
    CreateTraceEventInput,
    CreateTraceEventOutput,
    CreateTraceInput,
    CreateTraceOutput,
    ListTracesInput,
)
from modules.observability.application.use_cases import (
    CreateTraceEventUseCase,
    CreateTraceUseCase,
    GetTraceUseCase,
    ListTracesUseCase,
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

    async def list_by_project(
        self,
        project_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        return [
            trace for trace in self._storage.values() if trace.project_id == project_id
        ][offset : offset + limit]

    async def list_by_project_and_network(
        self,
        project_id: UUID,
        network_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        return [
            trace
            for trace in self._storage.values()
            if trace.project_id == project_id and trace.network_id == network_id
        ][offset : offset + limit]

    async def list_by_session(
        self,
        session_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        return [
            trace for trace in self._storage.values() if trace.session_id == session_id
        ][offset : offset + limit]

    async def list_by_project_and_agent(
        self,
        project_id: UUID,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Trace]:
        return [
            trace
            for trace in self._storage.values()
            if trace.project_id == project_id and trace.agent_id == agent_id
        ][offset : offset + limit]

    async def paginate_by_project(
        self,
        project_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ):
        raise NotImplementedError

    async def paginate_by_session(
        self,
        session_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ):
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

    async def list_by_trace(
        self,
        trace_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TraceEvent]:
        return [
            event for event in self._storage.values() if event.trace_id == trace_id
        ][offset : offset + limit]

    async def paginate_by_trace(
        self,
        trace_id: UUID,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ):
        raise NotImplementedError

    async def delete(self, event_id: UUID) -> None:
        self._storage.pop(event_id, None)


class FakeOutboxWriter:
    def __init__(self):
        self.written = []

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict,
        **kwargs,
    ) -> None:
        self.written.append((aggregate_type, aggregate_id, event_type, payload))


class TestCreateTraceUseCase:
    @pytest.mark.asyncio
    async def test_create_trace_success(self):
        repo = FakeTraceRepository()
        outbox = FakeOutboxWriter()
        uc = CreateTraceUseCase(repo, outbox)

        pid = UUID("00000000-0000-0000-0000-000000000001")
        result = await uc.execute(CreateTraceInput(project_id=pid, provider="openai"))

        assert isinstance(result, CreateTraceOutput)
        saved = await repo.get_by_id(result.trace_id)
        assert saved is not None
        assert saved.project_id == pid
        assert saved.provider == "openai"
        assert len(outbox.written) == 1
        assert outbox.written[0][0] == "Trace"
        assert outbox.written[0][2] == "trace.created.v1"


class TestCreateTraceEventUseCase:
    @pytest.mark.asyncio
    async def test_create_event_success(self):
        repo = FakeTraceEventRepository()
        outbox = FakeOutboxWriter()
        uc = CreateTraceEventUseCase(repo, outbox)

        tid = UUID("00000000-0000-0000-0000-000000000001")
        pid = UUID("00000000-0000-0000-0000-000000000002")
        result = await uc.execute(
            CreateTraceEventInput(
                trace_id=tid,
                project_id=pid,
                event_type="llm_call",
            )
        )

        assert isinstance(result, CreateTraceEventOutput)
        saved = await repo.get_by_id(result.event_id)
        assert saved is not None
        assert saved.trace_id == tid
        assert saved.event_type == TraceEventType.llm_call
        assert len(outbox.written) == 1
        assert outbox.written[0][0] == "TraceEvent"
        assert outbox.written[0][2] == "trace_event.created.v1"


class TestGetTraceUseCase:
    @pytest.mark.asyncio
    async def test_get_existing_trace(self):
        trace_repo = FakeTraceRepository()
        event_repo = FakeTraceEventRepository()
        uc = GetTraceUseCase(trace_repo, event_repo)

        pid = UUID("00000000-0000-0000-0000-000000000001")
        saved = await trace_repo.save(Trace(project_id=pid))
        result = await uc.execute(saved.id)
        assert result.id == saved.id
        assert result.project_id == pid

    @pytest.mark.asyncio
    async def test_get_nonexistent_trace_raises_error(self):
        uc = GetTraceUseCase(FakeTraceRepository(), FakeTraceEventRepository())
        with pytest.raises(NotFoundError):
            await uc.execute(UUID("00000000-0000-0000-0000-000000000099"))


class TestListTracesUseCase:
    @pytest.mark.asyncio
    async def test_list_by_project(self):
        repo = FakeTraceRepository()
        pid = UUID("00000000-0000-0000-0000-000000000001")
        await repo.save(Trace(project_id=pid))
        results = await ListTracesUseCase(repo).execute(
            ListTracesInput(project_id=pid)
        )
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_list_by_project_and_network(self):
        repo = FakeTraceRepository()
        pid = UUID("00000000-0000-0000-0000-000000000001")
        first_network = UUID("00000000-0000-0000-0000-000000000010")
        second_network = UUID("00000000-0000-0000-0000-000000000020")
        await repo.save(Trace(project_id=pid, network_id=first_network))
        await repo.save(Trace(project_id=pid, network_id=second_network))

        results = await ListTracesUseCase(repo).execute(
            ListTracesInput(project_id=pid, network_id=first_network)
        )

        assert len(results) == 1
        assert results[0].network_id == first_network

    @pytest.mark.asyncio
    async def test_list_without_project_returns_empty(self):
        results = await ListTracesUseCase(FakeTraceRepository()).execute(
            ListTracesInput()
        )
        assert results == []
