from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from modules.network.application.dtos.rerun import (
    NetworkRerunExecutionState,
    NetworkRerunSessionState,
    NetworkRerunSource,
)
from modules.network.application.interfaces.rerun_repository import (
    NetworkRerunRepository,
)
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


class SQLAlchemyNetworkRerunRepository(NetworkRerunRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    async def get_source(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> NetworkRerunSource | None:
        model = await self._uow.session.scalar(
            select(NetworkExecutionModel)
            .where(
                NetworkExecutionModel.id == execution_id,
                NetworkExecutionModel.project_id == project_id,
            )
            .with_for_update()
        )
        if model is None:
            return None
        return NetworkRerunSource(
            id=model.id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            network_session_id=model.network_session_id,
            project_id=model.project_id,
            input_message=model.input_message,
            draft_revision=model.draft_revision,
            definition_snapshot=deepcopy(model.definition_snapshot),
            resolved_bindings_snapshot=deepcopy(model.resolved_bindings_snapshot),
            status=str(model.status),
        )

    async def find_idempotent_execution(
        self,
        network_id: UUID,
        idempotency_key: str,
    ) -> NetworkRerunExecutionState | None:
        model = await self._uow.session.scalar(
            select(NetworkExecutionModel).where(
                NetworkExecutionModel.network_id == network_id,
                NetworkExecutionModel.idempotency_key == idempotency_key,
            )
        )
        if model is None:
            return None
        return NetworkRerunExecutionState(id=model.id, status=str(model.status))

    async def find_active_execution_id(
        self,
        network_session_id: UUID,
    ) -> UUID | None:
        return await self._uow.session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.status.in_(_ACTIVE_STATUSES),
            )
        )

    async def get_session_state(
        self,
        network_session_id: UUID,
    ) -> NetworkRerunSessionState | None:
        model = await self._uow.session.scalar(
            select(NetworkSessionModel)
            .where(NetworkSessionModel.id == network_session_id)
            .with_for_update()
        )
        if model is None:
            return None
        return NetworkRerunSessionState(
            id=model.id,
            status=str(model.status),
            environment=str(model.environment),
        )

    async def create_rerun(
        self,
        source: NetworkRerunSource,
        *,
        environment: str,
        idempotency_key: str | None,
    ) -> NetworkRerunExecutionState:
        rerun = NetworkExecutionModel(
            network_id=source.network_id,
            network_version_id=source.network_version_id,
            network_session_id=source.network_session_id,
            project_id=source.project_id,
            input_message=source.input_message,
            draft_revision=source.draft_revision,
            definition_snapshot=deepcopy(source.definition_snapshot),
            resolved_bindings_snapshot=deepcopy(source.resolved_bindings_snapshot),
            status="queued",
            idempotency_key=idempotency_key,
            last_event_sequence=1,
        )
        self._uow.session.add(rerun)
        await self._uow.session.flush()

        lineage = {
            "rerun_of_execution_id": str(source.id),
            "rerun_semantics": "new_logical_run",
            "session_semantics": "continue_existing_session",
        }
        self._uow.session.add_all(
            [
                NetworkMessageModel(
                    network_session_id=source.network_session_id,
                    network_execution_id=rerun.id,
                    project_id=source.project_id,
                    role="user",
                    content=source.input_message,
                    data=lineage,
                ),
                NetworkExecutionEventModel(
                    network_execution_id=rerun.id,
                    network_session_id=source.network_session_id,
                    sequence=1,
                    event_type="execution_accepted",
                    payload={
                        "status": "queued",
                        "rerun_of_execution_id": str(source.id),
                        "network_version_id": (
                            str(source.network_version_id)
                            if source.network_version_id
                            else None
                        ),
                        "draft_revision": source.draft_revision,
                        "session_semantics": "continue_existing_session",
                    },
                ),
                NetworkOutboxEventModel(
                    aggregate_type="network_execution",
                    aggregate_id=rerun.id,
                    event_type="network.execution.requested.v1",
                    event_version=1,
                    routing_key=f"network.execution.{environment}.requested.v1",
                    payload={
                        "execution_id": str(rerun.id),
                        "rerun_of_execution_id": str(source.id),
                    },
                    metadata_=lineage,
                    idempotency_key=f"network-execution:{rerun.id}:requested",
                    correlation_id=rerun.id,
                    causation_id=source.id,
                    status="pending",
                ),
            ]
        )
        network_session = await self._uow.session.get(
            NetworkSessionModel,
            source.network_session_id,
        )
        if network_session is not None:
            network_session.last_message_at = datetime.now(timezone.utc)
        return NetworkRerunExecutionState(id=rerun.id, status=str(rerun.status))
