from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from modules.network.application.dtos.execution import (
    AcceptedNetworkExecution,
    NetworkSessionAcceptanceState,
    NetworkVersionAcceptanceState,
    PersistNetworkExecutionInput,
)
from modules.network.application.interfaces.execution_repository import NetworkExecutionAcceptanceRepository
from modules.network.domain.entities import Network
from modules.network.infra.database.models import (
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkMessageModel,
    NetworkModel,
    NetworkOutboxEventModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkExecutionAcceptanceRepository(NetworkExecutionAcceptanceRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _execution(model: NetworkExecutionModel) -> AcceptedNetworkExecution:
        return AcceptedNetworkExecution(
            id=model.id,
            network_id=model.network_id,
            network_session_id=model.network_session_id,
            project_id=model.project_id,
            status=model.status,
            created_at=model.created_at,
        )

    @staticmethod
    def _network(model: NetworkModel) -> Network:
        return Network(
            id=model.id,
            project_id=model.project_id,
            name=model.name,
            description=model.description,
            draft_definition=model.draft_definition or {},
            draft_revision=model.draft_revision,
            staging_version_id=model.staging_version_id,
            production_version_id=model.production_version_id,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def get_session(self, *, network_id: UUID, project_id: UUID, network_session_id: UUID, lock: bool) -> NetworkSessionAcceptanceState | None:
        statement = select(NetworkSessionModel).where(
            NetworkSessionModel.id == network_session_id,
            NetworkSessionModel.network_id == network_id,
            NetworkSessionModel.project_id == project_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._uow.session.scalar(statement)
        if model is None:
            return None
        return NetworkSessionAcceptanceState(
            id=model.id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            project_id=model.project_id,
            environment=model.environment,
            status=model.status,
            origin=model.origin,
            chat_surface_id=model.chat_surface_id,
        )

    async def find_idempotent(self, *, network_id: UUID, idempotency_key: str) -> AcceptedNetworkExecution | None:
        model = await self._uow.session.scalar(
            select(NetworkExecutionModel).where(
                NetworkExecutionModel.network_id == network_id,
                NetworkExecutionModel.idempotency_key == idempotency_key,
            )
        )
        return self._execution(model) if model is not None else None

    async def find_active(self, network_session_id: UUID) -> AcceptedNetworkExecution | None:
        model = await self._uow.session.scalar(
            select(NetworkExecutionModel).where(
                NetworkExecutionModel.network_session_id == network_session_id,
                NetworkExecutionModel.status.in_({"queued", "running", "cancel_requested"}),
            )
        )
        return self._execution(model) if model is not None else None

    async def get_network(self, *, network_id: UUID, project_id: UUID, lock: bool) -> Network | None:
        statement = select(NetworkModel).where(
            NetworkModel.id == network_id,
            NetworkModel.project_id == project_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._uow.session.scalar(statement)
        return self._network(model) if model is not None else None

    async def get_version(self, *, version_id: UUID, network_id: UUID, project_id: UUID) -> NetworkVersionAcceptanceState | None:
        model = await self._uow.session.scalar(
            select(NetworkVersionModel).where(
                NetworkVersionModel.id == version_id,
                NetworkVersionModel.network_id == network_id,
                NetworkVersionModel.project_id == project_id,
            )
        )
        if model is None:
            return None
        return NetworkVersionAcceptanceState(
            id=model.id,
            network_id=model.network_id,
            project_id=model.project_id,
            version=model.version,
            definition=dict(model.definition or {}),
            resolved_bindings=dict(model.resolved_bindings or {}),
            composition_hash=model.composition_hash,
        )

    async def persist_acceptance(self, input_dto: PersistNetworkExecutionInput) -> AcceptedNetworkExecution:
        execution = NetworkExecutionModel(
            network_id=input_dto.network_id,
            network_version_id=input_dto.network_version_id,
            network_session_id=input_dto.network_session_id,
            project_id=input_dto.project_id,
            input_message=input_dto.message,
            draft_revision=input_dto.draft_revision,
            definition_snapshot=input_dto.definition_snapshot,
            resolved_bindings_snapshot=input_dto.resolved_bindings_snapshot,
            status="queued",
            idempotency_key=input_dto.idempotency_key,
            last_event_sequence=1,
        )
        self._uow.session.add(execution)
        await self._uow.session.flush()

        chat_surface_id = str(input_dto.chat_surface_id) if input_dto.chat_surface_id else None
        version_id = str(input_dto.network_version_id) if input_dto.network_version_id else None
        attribution = {
            "origin": input_dto.origin,
            "chat_surface_id": chat_surface_id,
            "network_session_id": str(input_dto.network_session_id),
            "network_version_id": version_id,
        }
        self._uow.session.add_all([
            NetworkMessageModel(
                network_session_id=input_dto.network_session_id,
                network_execution_id=execution.id,
                project_id=input_dto.project_id,
                role="user",
                content=input_dto.message,
                data=attribution if input_dto.chat_surface_id else None,
            ),
            NetworkExecutionEventModel(
                network_execution_id=execution.id,
                network_session_id=input_dto.network_session_id,
                sequence=1,
                event_type="execution_accepted",
                payload={
                    "status": "queued",
                    "environment": input_dto.environment,
                    "draft_revision": input_dto.draft_revision,
                    "network_version_id": version_id,
                    "network_version": input_dto.accepted_version,
                    "composition_hash": input_dto.accepted_composition_hash,
                    "root_node_id": str(input_dto.root_node_id),
                    "origin": input_dto.origin,
                    "chat_surface_id": chat_surface_id,
                    "limits": input_dto.limits,
                },
            ),
            NetworkOutboxEventModel(
                aggregate_type="network_execution",
                aggregate_id=execution.id,
                event_type="network.execution.requested.v1",
                event_version=1,
                routing_key=f"network.execution.{input_dto.environment}.requested.v1",
                payload={"execution_id": str(execution.id)},
                metadata_=attribution if input_dto.chat_surface_id else None,
                idempotency_key=f"network-execution:{execution.id}:requested",
                correlation_id=execution.id,
                causation_id=None,
                status="pending",
            ),
        ])
        network_session = await self._uow.session.get(NetworkSessionModel, input_dto.network_session_id)
        if network_session is None:
            raise RuntimeError("Network Session disappeared during execution acceptance")
        network_session.last_message_at = datetime.now(timezone.utc)
        await self._uow.session.flush()
        return self._execution(execution)
