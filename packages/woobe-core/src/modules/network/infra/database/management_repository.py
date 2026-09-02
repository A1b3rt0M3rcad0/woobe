from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.network.application.dtos.management import (
    ManagedNetworkVersion,
    NetworkProductionActivation,
    NetworkProductionState,
)
from modules.network.application.interfaces.management_repository import (
    NetworkManagementRepository,
)
from modules.network.infra.database.models import (
    NetworkAgentContextModel,
    NetworkExecutionEventModel,
    NetworkExecutionModel,
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from modules.network.infra.database.schema_extensions import (
    NetworkProductionActivationModel,
    version_extension_payload,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkManagementRepository(NetworkManagementRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _version(model: NetworkVersionModel) -> ManagedNetworkVersion:
        return ManagedNetworkVersion(
            id=model.id,
            network_id=model.network_id,
            project_id=model.project_id,
            kind=str(model.kind),
            version=str(model.version),
            composition_hash=str(model.composition_hash),
            definition=dict(model.definition or {}),
            resolved_bindings=dict(model.resolved_bindings or {}),
            created_at=model.created_at,
            created_by=model.created_by,
            source_version_id=model.source_version_id,
            activation_kind=model.activation_kind,
            change_description=model.change_description,
            extensions=version_extension_payload(model),
        )

    @staticmethod
    def _activation(
        model: NetworkProductionActivationModel,
    ) -> NetworkProductionActivation:
        return NetworkProductionActivation(
            id=model.id,
            network_id=model.network_id,
            version_id=model.version_id,
            previous_version_id=model.previous_version_id,
            activation_kind=model.activation_kind,
            change_description=model.change_description,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    async def list_versions(
        self,
        network_id: UUID,
        project_id: UUID,
    ) -> list[ManagedNetworkVersion]:
        result = await self._uow.session.scalars(
            select(NetworkVersionModel)
            .where(
                NetworkVersionModel.network_id == network_id,
                NetworkVersionModel.project_id == project_id,
            )
            .order_by(NetworkVersionModel.created_at.desc())
        )
        return [self._version(model) for model in result.all()]

    async def list_activations(
        self,
        network_id: UUID,
        project_id: UUID,
    ) -> list[NetworkProductionActivation]:
        result = await self._uow.session.scalars(
            select(NetworkProductionActivationModel)
            .where(
                NetworkProductionActivationModel.network_id == network_id,
                NetworkProductionActivationModel.project_id == project_id,
            )
            .order_by(NetworkProductionActivationModel.created_at.desc())
        )
        return [self._activation(model) for model in result.all()]

    async def get_execution_snapshot(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        execution = await self._uow.session.get(NetworkExecutionModel, execution_id)
        if execution is None or execution.project_id != project_id:
            return None
        network_session = await self._uow.session.get(
            NetworkSessionModel,
            execution.network_session_id,
        )
        if network_session is None or network_session.project_id != project_id:
            return None

        snapshot_source = "execution"
        definition = execution.definition_snapshot
        bindings = execution.resolved_bindings_snapshot
        version_label = (
            f"Draft r{execution.draft_revision}"
            if execution.draft_revision is not None
            else None
        )
        if execution.network_version_id is not None:
            version = await self._uow.session.get(
                NetworkVersionModel,
                execution.network_version_id,
            )
            if (
                version is None
                or version.project_id != project_id
                or version.network_id != execution.network_id
            ):
                return None
            snapshot_source = "network_version"
            definition = version.definition
            bindings = version.resolved_bindings
            version_label = version.version

        if not definition or bindings is None:
            return None

        events = list(
            (
                await self._uow.session.scalars(
                    select(NetworkExecutionEventModel)
                    .where(
                        NetworkExecutionEventModel.network_execution_id
                        == execution.id
                    )
                    .order_by(NetworkExecutionEventModel.sequence)
                )
            ).all()
        )
        accepted = next(
            (item for item in events if item.event_type == "execution_accepted"),
            None,
        )
        composition_hash = (
            str((accepted.payload or {}).get("composition_hash"))
            if accepted and (accepted.payload or {}).get("composition_hash")
            else None
        )

        contexts = list(
            (
                await self._uow.session.scalars(
                    select(NetworkAgentContextModel).where(
                        NetworkAgentContextModel.network_session_id
                        == execution.network_session_id
                    )
                )
            ).all()
        )
        contexts_by_node: dict[str, dict[str, Any]] = {
            str(item.network_node_id): {
                "node_id": str(item.network_node_id),
                "agent_id": str(item.agent_id),
                "agent_session_id": (
                    str(item.agent_session_id) if item.agent_session_id else None
                ),
            }
            for item in contexts
        }
        for event in events:
            if event.node_id is None or event.agent_id is None:
                continue
            data = event.payload or {}
            node_id = str(event.node_id)
            context = contexts_by_node.setdefault(
                node_id,
                {
                    "node_id": node_id,
                    "agent_id": str(event.agent_id),
                    "agent_session_id": None,
                },
            )
            if data.get("agent_session_id"):
                context["agent_session_id"] = str(data["agent_session_id"])
            for field in ("source", "version", "provider", "model"):
                if data.get(field):
                    context[field] = str(data[field])

        return {
            "execution_id": str(execution.id),
            "network_id": str(execution.network_id),
            "network_session_id": str(execution.network_session_id),
            "environment": network_session.environment,
            "draft_revision": execution.draft_revision,
            "network_version_id": (
                str(execution.network_version_id)
                if execution.network_version_id
                else None
            ),
            "version_label": version_label,
            "composition_hash": composition_hash,
            "definition": definition,
            "resolved_bindings": bindings,
            "snapshot_source": snapshot_source,
            "agent_contexts": list(contexts_by_node.values()),
            "parsed_output": getattr(execution, "parsed_output", None),
            "output_parse_error": getattr(execution, "output_parse_error", None),
        }

    async def get_production_state(
        self,
        network_id: UUID,
        project_id: UUID,
        *,
        lock: bool,
    ) -> NetworkProductionState | None:
        query = select(NetworkModel).where(
            NetworkModel.id == network_id,
            NetworkModel.project_id == project_id,
        )
        if lock:
            query = query.with_for_update()
        network = await self._uow.session.scalar(query)
        if network is None:
            return None
        return NetworkProductionState(
            network_id=network.id,
            project_id=network.project_id,
            production_version_id=network.production_version_id,
        )

    async def get_version(
        self,
        version_id: UUID,
        project_id: UUID,
    ) -> ManagedNetworkVersion | None:
        model = await self._uow.session.scalar(
            select(NetworkVersionModel).where(
                NetworkVersionModel.id == version_id,
                NetworkVersionModel.project_id == project_id,
            )
        )
        return self._version(model) if model is not None else None

    async def activate_production(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        version_id: UUID,
        previous_version_id: UUID | None,
        activation_kind: str,
        change_description: str,
        created_by: UUID | None,
    ) -> NetworkProductionActivation:
        network = await self._uow.session.scalar(
            select(NetworkModel)
            .where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
            .with_for_update()
        )
        if network is None:
            raise RuntimeError("Network disappeared during Production activation")
        activation = NetworkProductionActivationModel(
            network_id=network_id,
            project_id=project_id,
            version_id=version_id,
            previous_version_id=previous_version_id,
            activation_kind=activation_kind,
            change_description=change_description,
            created_by=created_by,
        )
        self._uow.session.add(activation)
        network.production_version_id = version_id
        await self._uow.session.flush()
        return self._activation(activation)
