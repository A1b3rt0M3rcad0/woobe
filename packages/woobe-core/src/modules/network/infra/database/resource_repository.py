from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from modules.network.application.interfaces.resource_repository import (
    NetworkResourceRepository,
)
from modules.network.domain.entities import Network
from modules.network.infra.database.models import NetworkModel
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.contracts.errors import ConflictError


class SQLAlchemyNetworkResourceRepository(NetworkResourceRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    @staticmethod
    def _to_domain(model: NetworkModel) -> Network:
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

    async def list_by_project(self, project_id: UUID) -> list[Network]:
        result = await self._uow.session.scalars(
            select(NetworkModel)
            .where(NetworkModel.project_id == project_id)
            .order_by(NetworkModel.updated_at.desc(), NetworkModel.created_at.desc())
        )
        return [self._to_domain(model) for model in result.all()]

    async def get_for_project(
        self,
        project_id: UUID,
        network_id: UUID,
    ) -> Network | None:
        model = await self._uow.session.scalar(
            select(NetworkModel).where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
        )
        return self._to_domain(model) if model is not None else None

    async def name_exists(
        self,
        project_id: UUID,
        name: str,
        *,
        exclude_network_id: UUID | None = None,
    ) -> bool:
        query = select(NetworkModel.id).where(
            NetworkModel.project_id == project_id,
            func.lower(func.btrim(NetworkModel.name)) == name.lower(),
        )
        if exclude_network_id is not None:
            query = query.where(NetworkModel.id != exclude_network_id)
        return await self._uow.session.scalar(query) is not None

    async def create(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
    ) -> Network:
        model = NetworkModel(
            project_id=project_id,
            name=name,
            description=description,
            draft_definition={},
            draft_revision=0,
            staging_version_id=None,
            production_version_id=None,
        )
        self._uow.session.add(model)
        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A Network with this name already exists in the Project"
            ) from exc
        return self._to_domain(model)

    async def update_metadata(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        name: str | None,
        description: str | None,
    ) -> Network | None:
        model = await self._uow.session.scalar(
            select(NetworkModel)
            .where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
            .with_for_update()
        )
        if model is None:
            return None
        if name is not None:
            model.name = name
        if description is not None:
            model.description = description
        try:
            await self._uow.session.flush()
        except IntegrityError as exc:
            raise ConflictError(
                "A Network with this name already exists in the Project"
            ) from exc
        return self._to_domain(model)
