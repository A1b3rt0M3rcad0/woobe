from collections import defaultdict
from uuid import UUID

from sqlalchemy import delete, func, select

from modules.network.application.dtos.history import (
    NetworkExecutionEventOutput,
    NetworkExecutionHistoryOutput,
    NetworkMessageHistoryOutput,
    NetworkSessionHistoryOutput,
)
from modules.network.application.interfaces.history_repository import (
    NetworkHistoryRepository,
)
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkSessionModel,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkHistoryRepository(NetworkHistoryRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _event_output(event: NetworkExecutionEventModel) -> NetworkExecutionEventOutput:
        return NetworkExecutionEventOutput(
            id=event.id,
            sequence=event.sequence,
            event_type=event.event_type,
            invocation_id=event.invocation_id,
            parent_invocation_id=event.parent_invocation_id,
            node_id=event.node_id,
            agent_id=event.agent_id,
            depth=event.depth,
            payload=event.payload or {},
            created_at=event.created_at,
        )

    async def list_sessions(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        limit: int = 100,
    ) -> list[NetworkSessionHistoryOutput]:
        message_count = (
            select(func.count(NetworkMessageModel.id))
            .where(NetworkMessageModel.network_session_id == NetworkSessionModel.id)
            .correlate(NetworkSessionModel)
            .scalar_subquery()
        )
        execution_count = (
            select(func.count(NetworkExecutionModel.id))
            .where(NetworkExecutionModel.network_session_id == NetworkSessionModel.id)
            .correlate(NetworkSessionModel)
            .scalar_subquery()
        )
        result = await self._uow.session.execute(
            select(
                NetworkSessionModel,
                message_count.label("message_count"),
                execution_count.label("trace_count"),
            )
            .where(
                NetworkSessionModel.network_id == network_id,
                NetworkSessionModel.project_id == project_id,
            )
            .order_by(NetworkSessionModel.created_at.desc())
            .limit(limit)
        )
        return [
            NetworkSessionHistoryOutput(
                id=session.id,
                network_version_id=session.network_version_id,
                environment=session.environment,
                title=session.title,
                status=session.status,
                last_message_at=session.last_message_at,
                created_at=session.created_at,
                message_count=int(message_count_value or 0),
                trace_count=int(trace_count_value or 0),
            )
            for session, message_count_value, trace_count_value in result.all()
        ]

    async def session_exists(
        self,
        *,
        network_id: UUID,
        network_session_id: UUID,
        project_id: UUID,
    ) -> bool:
        session_id = await self._uow.session.scalar(
            select(NetworkSessionModel.id).where(
                NetworkSessionModel.id == network_session_id,
                NetworkSessionModel.network_id == network_id,
                NetworkSessionModel.project_id == project_id,
            )
        )
        return session_id is not None

    async def list_messages(
        self,
        *,
        network_session_id: UUID,
        project_id: UUID,
        offset: int,
        limit: int,
    ) -> list[NetworkMessageHistoryOutput]:
        result = await self._uow.session.execute(
            select(NetworkMessageModel, NetworkExecutionModel)
            .outerjoin(
                NetworkExecutionModel,
                NetworkExecutionModel.id == NetworkMessageModel.network_execution_id,
            )
            .where(
                NetworkMessageModel.network_session_id == network_session_id,
                NetworkMessageModel.project_id == project_id,
            )
            .order_by(NetworkMessageModel.created_at.asc())
            .offset(offset)
            .limit(limit)
        )
        rows = list(result.all())
        execution_ids = {
            execution.id for _, execution in rows if execution is not None
        }
        events_by_execution: dict[UUID, list[NetworkExecutionEventOutput]] = defaultdict(list)
        if execution_ids:
            event_result = await self._uow.session.scalars(
                select(NetworkExecutionEventModel)
                .where(NetworkExecutionEventModel.network_execution_id.in_(execution_ids))
                .order_by(
                    NetworkExecutionEventModel.network_execution_id,
                    NetworkExecutionEventModel.sequence,
                )
            )
            for event in event_result.all():
                events_by_execution[event.network_execution_id].append(
                    self._event_output(event)
                )

        output: list[NetworkMessageHistoryOutput] = []
        for message, execution in rows:
            execution_output = None
            if execution is not None:
                events = events_by_execution[execution.id]
                failure = next(
                    (
                        event.payload
                        for event in reversed(events)
                        if event.event_type == "execution_failed"
                    ),
                    None,
                )
                execution_output = NetworkExecutionHistoryOutput(
                    id=execution.id,
                    status=execution.status,
                    draft_revision=execution.draft_revision,
                    network_version_id=execution.network_version_id,
                    root_trace_id=execution.root_trace_id,
                    failure_code=execution.failure_code,
                    failure=failure,
                    started_at=execution.started_at,
                    completed_at=execution.completed_at,
                    events=events,
                )
            output.append(
                NetworkMessageHistoryOutput(
                    id=message.id,
                    network_execution_id=message.network_execution_id,
                    role=message.role,
                    content=message.content,
                    data=message.data,
                    created_at=message.created_at,
                    execution=execution_output,
                )
            )
        return output

    async def has_active_execution(self, network_session_id: UUID) -> bool:
        execution_id = await self._uow.session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.status.in_(
                    {"queued", "running", "cancel_requested"}
                ),
            )
        )
        return execution_id is not None

    async def clear_agent_contexts(self, network_session_id: UUID) -> None:
        await self._uow.session.execute(
            delete(NetworkAgentContextModel).where(
                NetworkAgentContextModel.network_session_id == network_session_id
            )
        )

    async def execution_exists(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> bool:
        value = await self._uow.session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.id == execution_id,
                NetworkExecutionModel.project_id == project_id,
            )
        )
        return value is not None

    async def list_execution_events(
        self,
        *,
        execution_id: UUID,
        after_sequence: int,
        limit: int,
    ) -> list[NetworkExecutionEventOutput]:
        result = await self._uow.session.scalars(
            select(NetworkExecutionEventModel)
            .where(
                NetworkExecutionEventModel.network_execution_id == execution_id,
                NetworkExecutionEventModel.sequence > after_sequence,
            )
            .order_by(NetworkExecutionEventModel.sequence.asc())
            .limit(limit)
        )
        return [self._event_output(event) for event in result.all()]
