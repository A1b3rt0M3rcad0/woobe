from datetime import datetime, timezone
from uuid import UUID

from modules.network.application.dtos.execution import NetworkExecutionControlState
from modules.network.application.interfaces.execution_control import (
    NetworkExecutionControlRepository,
)
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkExecutionControlRepository(NetworkExecutionControlRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _state(model: NetworkExecutionModel) -> NetworkExecutionControlState:
        return NetworkExecutionControlState(
            id=model.id,
            network_id=model.network_id,
            network_session_id=model.network_session_id,
            project_id=model.project_id,
            status=str(model.status),
            created_at=model.created_at,
        )

    async def get_execution(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkExecutionControlState | None:
        model = await self._uow.session.get(NetworkExecutionModel, execution_id)
        if model is None or model.project_id != project_id:
            return None
        return self._state(model)

    async def request_durable_cancellation(
        self,
        *,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkExecutionControlState | None:
        model = await self._uow.session.get(
            NetworkExecutionModel,
            execution_id,
            with_for_update=True,
        )
        if model is None or model.project_id != project_id:
            return None
        if str(model.status) not in {"queued", "running"}:
            return self._state(model)

        now = datetime.now(timezone.utc)
        model.cancel_requested_at = now
        if str(model.status) == "queued":
            model.status = "cancelled"
            model.completed_at = now
            model.last_event_sequence += 1
            self._uow.session.add(
                NetworkExecutionEventModel(
                    network_execution_id=model.id,
                    network_session_id=model.network_session_id,
                    sequence=model.last_event_sequence,
                    event_type="execution_cancelled",
                    payload={"cancelled_before_start": True},
                )
            )
        else:
            model.status = "cancel_requested"
        await self._uow.session.flush()
        return self._state(model)
