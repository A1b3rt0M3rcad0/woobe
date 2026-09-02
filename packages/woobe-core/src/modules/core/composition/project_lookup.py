from __future__ import annotations

from uuid import UUID

from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.repositories import SQLAlchemyProjectRepository
from modules.core.infra.database.unit_of_work import CoreUnitOfWork


class CoreProjectLookup:
    """Public read-only Project lookup for other bounded contexts."""

    async def exists(self, project_id: UUID) -> bool:
        uow = CoreUnitOfWork(DATABASE_ENGINE).mark_read_only()
        repository = SQLAlchemyProjectRepository(uow)
        async with uow:
            return await repository.get_by_id(project_id) is not None


__all__ = ["CoreProjectLookup"]
