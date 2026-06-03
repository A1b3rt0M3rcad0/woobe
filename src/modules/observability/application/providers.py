from sqlalchemy.ext.asyncio import AsyncSession

from modules.observability.infra.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyTraceEventRepository,
    SQLAlchemyTraceRepository,
)
from modules.observability.service.use_cases import (
    CreateTraceEventUseCase,
    CreateTraceUseCase,
    GetTraceUseCase,
)


class ObservabilityProviders:

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def create_trace_use_case(self) -> CreateTraceUseCase:
        return CreateTraceUseCase(
            repo=SQLAlchemyTraceRepository(self._session),
            outbox=SQLAlchemyOutboxEventWriter(self._session),
        )

    def create_trace_event_use_case(self) -> CreateTraceEventUseCase:
        return CreateTraceEventUseCase(
            repo=SQLAlchemyTraceEventRepository(self._session),
            outbox=SQLAlchemyOutboxEventWriter(self._session),
        )

    def get_trace_use_case(self) -> GetTraceUseCase:
        return GetTraceUseCase(
            trace_repo=SQLAlchemyTraceRepository(self._session),
            event_repo=SQLAlchemyTraceEventRepository(self._session),
        )
