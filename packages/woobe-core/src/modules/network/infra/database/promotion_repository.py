from uuid import UUID

from sqlalchemy import select

from modules.network.application.dtos.management import ManagedNetworkVersion
from modules.network.application.dtos.promotion import CreateNetworkPromotionVersionInput
from modules.network.application.interfaces.promotion_repository import (
    NetworkPromotionRepository,
)
from modules.network.domain.entities import Network
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.schema_extensions import (
    NetworkProductionActivationModel,
    version_extension_payload,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkPromotionRepository(NetworkPromotionRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

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

    @staticmethod
    def _version(model: NetworkVersionModel) -> ManagedNetworkVersion:
        return ManagedNetworkVersion(
            id=model.id,
            network_id=model.network_id,
            project_id=model.project_id,
            kind=model.kind,
            version=model.version,
            composition_hash=model.composition_hash,
            definition=dict(model.definition or {}),
            resolved_bindings=dict(model.resolved_bindings or {}),
            created_at=model.created_at,
            created_by=model.created_by,
            source_version_id=model.source_version_id,
            activation_kind=model.activation_kind,
            change_description=model.change_description,
            extensions=version_extension_payload(model),
        )

    async def get_network(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        lock: bool,
    ) -> Network | None:
        statement = select(NetworkModel).where(
            NetworkModel.id == network_id,
            NetworkModel.project_id == project_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._uow.session.scalar(statement)
        return self._network(model) if model is not None else None

    async def get_version(
        self,
        *,
        version_id: UUID,
        project_id: UUID,
        network_id: UUID,
        lock: bool,
    ) -> ManagedNetworkVersion | None:
        statement = select(NetworkVersionModel).where(
            NetworkVersionModel.id == version_id,
            NetworkVersionModel.project_id == project_id,
            NetworkVersionModel.network_id == network_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._uow.session.scalar(statement)
        return self._version(model) if model is not None else None

    async def list_version_names(self, network_id: UUID, kind: str) -> list[str]:
        result = await self._uow.session.scalars(
            select(NetworkVersionModel.version).where(
                NetworkVersionModel.network_id == network_id,
                NetworkVersionModel.kind == kind,
            )
        )
        return list(result.all())

    async def find_by_fingerprint(
        self,
        *,
        network_id: UUID,
        kind: str,
        fingerprint: str,
    ) -> ManagedNetworkVersion | None:
        model = await self._uow.session.scalar(
            select(NetworkVersionModel)
            .where(
                NetworkVersionModel.network_id == network_id,
                NetworkVersionModel.kind == kind,
                NetworkVersionModel.release_fingerprint == fingerprint,
            )
            .order_by(NetworkVersionModel.created_at.desc())
            .limit(1)
        )
        return self._version(model) if model is not None else None

    async def create_version(
        self,
        input_dto: CreateNetworkPromotionVersionInput,
    ) -> ManagedNetworkVersion:
        model = NetworkVersionModel(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            kind=input_dto.kind,
            version=input_dto.version,
            definition=input_dto.definition,
            resolved_bindings=input_dto.resolved_bindings,
            composition_hash=input_dto.composition_hash,
            created_by=input_dto.created_by,
            activation_kind=input_dto.activation_kind,
            change_description=input_dto.change_description,
        )
        model.source_draft_revision = input_dto.source_draft_revision
        model.source_staging_version_id = input_dto.source_staging_version_id
        model.entry_agent_id = input_dto.entry_agent_id
        model.entry_agent_release_id = input_dto.entry_agent_release_id
        model.entry_agent_release_version = input_dto.entry_agent_release_version
        model.public_output_contract = input_dto.public_output_contract
        model.public_output_contract_hash = input_dto.public_output_contract_hash
        model.agent_release_manifest = input_dto.agent_release_manifest
        model.agent_release_manifest_hash = input_dto.agent_release_manifest_hash
        model.runtime_settings_hash = input_dto.runtime_settings_hash
        model.release_fingerprint = input_dto.release_fingerprint
        model.change_kind = input_dto.change_kind
        self._uow.session.add(model)
        await self._uow.session.flush()
        return self._version(model)

    async def set_staging_version(self, network_id: UUID, version_id: UUID) -> None:
        model = await self._uow.session.get(NetworkModel, network_id)
        if model is None:
            raise RuntimeError("Network disappeared while staging")
        model.staging_version_id = version_id

    async def set_production_version(self, network_id: UUID, version_id: UUID) -> None:
        model = await self._uow.session.get(NetworkModel, network_id)
        if model is None:
            raise RuntimeError("Network disappeared while publishing")
        model.production_version_id = version_id

    async def record_activation(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        version_id: UUID,
        previous_version_id: UUID | None,
        activation_kind: str,
        change_description: str,
        created_by: UUID | None,
    ) -> None:
        self._uow.session.add(
            NetworkProductionActivationModel(
                network_id=network_id,
                project_id=project_id,
                version_id=version_id,
                previous_version_id=previous_version_id,
                activation_kind=activation_kind,
                change_description=change_description,
                created_by=created_by,
            )
        )
        await self._uow.session.flush()
