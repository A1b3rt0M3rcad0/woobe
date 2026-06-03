from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.domain.repositories import TraceRepository
from modules.observability.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from shared.domain.events import OutboxEventWriter


class ObservabilityProviders:

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def create_trace_use_case(self):
        from modules.observability.service.use_cases import CreateTraceUseCase
        repo: TraceRepository = SQLAlchemyTraceRepository(self.session)
        outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(self.session)
        return CreateTraceUseCase(repo, outbox)

    def create_trace_event_use_case(self):
        from modules.observability.service.use_cases import CreateTraceEventUseCase
        trace_repo: TraceRepository = SQLAlchemyTraceRepository(self.session)
        event_repo = SQLAlchemyTraceEventRepository(self.session)
        outbox: OutboxEventWriter = SQLAlchemyOutboxEventWriter(self.session)
        return CreateTraceEventUseCase(trace_repo, event_repo, outbox)

    def get_trace_use_case(self):
        repo: TraceRepository = SQLAlchemyTraceRepository(self.session)
        return _GetTraceUseCase(repo)

    def list_traces_use_case(self):
        repo: TraceRepository = SQLAlchemyTraceRepository(self.session)
        return _ListTracesUseCase(repo)


class _GetTraceUseCase:
    def __init__(self, repo: TraceRepository):
        self._repo = repo

    async def execute(self, trace_id: UUID):
        from shared.domain.errors import NotFoundError
        trace = await self._repo.get_by_id(trace_id)
        if trace is None:
            raise NotFoundError(f"Trace {trace_id} not found")
        return trace


class _ListTracesUseCase:
    def __init__(self, repo: TraceRepository):
        self._repo = repo

    async def execute(self, project_id: UUID, limit: int = 100, offset: int = 0):
        return await self._repo.list_by_project(project_id, limit, offset)
