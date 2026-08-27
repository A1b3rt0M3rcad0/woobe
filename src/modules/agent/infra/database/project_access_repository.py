from __future__ import annotations

from uuid import UUID

from modules.agent.application.interfaces.project_access_repository import (
    ProjectAccessRepository,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from shared.security.tenancy import TenantAuthorizer


class SQLAlchemyProjectAccessRepository(ProjectAccessRepository):
    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def require_user_access(
        self,
        *,
        user_id: UUID,
        project_id: UUID,
    ) -> None:
        await TenantAuthorizer(self._uow.session).authorize(
            user_id=user_id,
            path_params={},
            query_params={"project_id": project_id},
            body=None,
        )
