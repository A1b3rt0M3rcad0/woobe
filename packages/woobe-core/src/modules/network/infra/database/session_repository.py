from uuid import UUID

from modules.network.application.interfaces.session_repository import (
    NetworkRuntimeEnvironmentRepository,
    NetworkSessionRepository,
)
from modules.network.domain.entities import NetworkSession
from modules.network.domain.enums import NetworkEnvironment, NetworkSessionStatus
from modules.network.infra.database.models import NetworkSessionModel
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.runtime_environment import assert_runtime_environment_enabled


class SQLAlchemyNetworkSessionRepository(NetworkSessionRepository):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    async def create(self, session: NetworkSession) -> NetworkSession:
        model = NetworkSessionModel(
            id=session.id,
            network_id=session.network_id,
            network_version_id=session.network_version_id,
            project_id=session.project_id,
            environment=session.environment.value,
            title=session.title,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            external_session_id=session.external_session_id,
            status=session.status.value,
        )
        self._uow.session.add(model)
        await self._uow.session.flush()
        return NetworkSession(
            id=model.id,
            network_id=model.network_id,
            network_version_id=model.network_version_id,
            project_id=model.project_id,
            environment=NetworkEnvironment(model.environment),
            title=model.title,
            tenant_id=model.tenant_id,
            user_id=model.user_id,
            external_session_id=model.external_session_id,
            status=NetworkSessionStatus(model.status),
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class SQLAlchemyNetworkRuntimeEnvironmentRepository(
    NetworkRuntimeEnvironmentRepository
):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    async def require_enabled(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: str,
    ) -> None:
        await assert_runtime_environment_enabled(
            self._uow.session,
            target_type="network",
            target_id=network_id,
            project_id=project_id,
            environment=environment,
        )
