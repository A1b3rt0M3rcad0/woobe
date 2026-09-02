from typing import Any
from uuid import UUID

from sqlalchemy import select, update

from modules.network.application.interfaces.draft_repository import (
    NetworkDraftRepository,
)
from modules.network.domain.entities import Network
from modules.network.infra.database.models import NetworkModel
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkDraftRepository(NetworkDraftRepository):
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

    async def get_for_project(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
    ) -> Network | None:
        model = await self._uow.session.scalar(
            select(NetworkModel).where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
            )
        )
        return self._to_domain(model) if model is not None else None

    async def save_draft(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        expected_revision: int,
        definition: dict[str, Any],
    ) -> Network | None:
        result = await self._uow.session.execute(
            update(NetworkModel)
            .where(
                NetworkModel.id == network_id,
                NetworkModel.project_id == project_id,
                NetworkModel.draft_revision == expected_revision,
            )
            .values(
                draft_definition=definition,
                draft_revision=NetworkModel.draft_revision + 1,
            )
            .returning(NetworkModel)
        )
        model = result.scalar_one_or_none()
        return self._to_domain(model) if model is not None else None
