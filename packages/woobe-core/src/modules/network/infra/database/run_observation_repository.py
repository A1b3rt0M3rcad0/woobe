from datetime import datetime
from uuid import UUID

from sqlalchemy import select

from modules.network.application.dtos.observation import NetworkRunObservation
from modules.network.application.interfaces.run_observation_repository import (
    NetworkRunObservationRepository,
)
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkSessionModel,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


class SQLAlchemyNetworkRunObservationRepository(NetworkRunObservationRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _observation(
        execution: NetworkExecutionModel,
        network_session: NetworkSessionModel,
    ) -> NetworkRunObservation:
        return NetworkRunObservation(
            id=execution.id,
            network_id=execution.network_id,
            network_version_id=execution.network_version_id,
            network_session_id=execution.network_session_id,
            project_id=execution.project_id,
            environment=network_session.environment,
            status=str(execution.status),
            input_message=execution.input_message,
            output_message=execution.output_message,
            parsed_output=execution.parsed_output,
            output_parse_error=execution.output_parse_error,
            root_trace_id=execution.root_trace_id,
            failure_code=execution.failure_code,
            failure_detail=execution.failure_detail,
            created_at=execution.created_at,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            updated_at=execution.updated_at,
        )

    async def get(self, execution_id: UUID) -> NetworkRunObservation | None:
        execution = await self._uow.session.get(NetworkExecutionModel, execution_id)
        if execution is None:
            return None
        network_session = await self._uow.session.get(
            NetworkSessionModel,
            execution.network_session_id,
        )
        if network_session is None:
            return None
        return self._observation(execution, network_session)

    async def find_active(
        self,
        *,
        network_session_id: UUID | None = None,
        network_id: UUID | None = None,
        environment: str | None = None,
    ) -> NetworkRunObservation | None:
        statement = (
            select(NetworkExecutionModel, NetworkSessionModel)
            .join(
                NetworkSessionModel,
                NetworkSessionModel.id == NetworkExecutionModel.network_session_id,
            )
            .where(NetworkExecutionModel.status.in_(_ACTIVE_STATUSES))
        )
        if network_session_id is not None:
            statement = statement.where(
                NetworkExecutionModel.network_session_id == network_session_id
            )
        if network_id is not None:
            statement = statement.where(NetworkExecutionModel.network_id == network_id)
        if environment is not None:
            statement = statement.where(NetworkSessionModel.environment == environment)
        row = (
            await self._uow.session.execute(
                statement
                .order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        execution, network_session = row
        return self._observation(execution, network_session)

    async def find_latest(
        self,
        *,
        network_session_id: UUID,
        network_id: UUID,
        project_id: UUID,
        network_version_id: UUID | None,
        created_after: datetime | None = None,
    ) -> NetworkRunObservation | None:
        statement = (
            select(NetworkExecutionModel, NetworkSessionModel)
            .join(
                NetworkSessionModel,
                NetworkSessionModel.id == NetworkExecutionModel.network_session_id,
            )
            .where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.network_id == network_id,
                NetworkExecutionModel.project_id == project_id,
                NetworkExecutionModel.network_version_id == network_version_id,
            )
        )
        if created_after is not None:
            statement = statement.where(NetworkExecutionModel.created_at >= created_after)
        row = (
            await self._uow.session.execute(
                statement
                .order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        execution, network_session = row
        return self._observation(execution, network_session)
