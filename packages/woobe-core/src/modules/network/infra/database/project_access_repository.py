from uuid import UUID

from modules.network.application.interfaces.project_access_repository import (
    NetworkProjectAccessRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.security.tenancy import TenantAuthorizer


class SQLAlchemyNetworkProjectAccessRepository(NetworkProjectAccessRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
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
