from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from modules.agent.entrypoint import NetworkAgentPromotionGateway
from modules.network.application.dtos.execution import (
    AcceptNetworkExecutionInput,
    CancelNetworkExecutionInput,
)
from modules.network.application.dtos.observation import NetworkRunObservation
from modules.network.application.use_cases.execution_control_use_cases import (
    CancelNetworkExecutionUseCase,
)
from modules.network.application.use_cases.execution_use_cases import (
    AcceptNetworkExecutionUseCase,
)
from modules.network.composition.factories.network_uow_factory import build_network_read_uow
from modules.network.composition.resources import DATABASE_ENGINE, EXECUTION_STATE_STORE, SETTINGS
from modules.network.infra.database.execution_control_repository import (
    SQLAlchemyNetworkExecutionControlRepository,
)
from modules.network.infra.database.execution_repository import (
    SQLAlchemyNetworkExecutionAcceptanceRepository,
)
from modules.network.infra.database.runtime_transaction_runner import (
    NetworkRuntimeTransactionRunner,
)
from modules.network.infra.database.session_repository import (
    SQLAlchemyNetworkRuntimeEnvironmentRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.infra.execution.network_run_reattach_service import (
    NetworkRunReattachService,
)
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from shared.contracts.errors import NotFoundError


@dataclass(frozen=True, slots=True)
class NetworkChatSurfaceRun:
    id: UUID
    project_id: UUID
    network_id: UUID
    network_session_id: UUID
    network_version_id: UUID | None
    environment: str
    status: str
    input_message: str
    created_at: datetime | None


class NetworkChatSurfaceRuntime:
    """Public Network boundary used by ChatSurface without leaking Network internals."""

    def __init__(self) -> None:
        self._observation = NetworkRunReattachService(
            transactions=NetworkRuntimeTransactionRunner(build_network_read_uow),
            state_store=EXECUTION_STATE_STORE,
            heartbeat_seconds=SETTINGS.network_stream_heartbeat_seconds,
        )

    @staticmethod
    def _view(run: NetworkRunObservation) -> NetworkChatSurfaceRun:
        return NetworkChatSurfaceRun(
            id=run.id,
            project_id=run.project_id,
            network_id=run.network_id,
            network_session_id=run.network_session_id,
            network_version_id=run.network_version_id,
            environment=run.environment,
            status=run.status,
            input_message=run.input_message,
            created_at=run.created_at,
        )

    async def submit(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
        message: str,
        idempotency_key: str,
    ) -> NetworkChatSurfaceRun:
        async with NetworkUnitOfWork(DATABASE_ENGINE) as uow:
            repository = SQLAlchemyNetworkExecutionAcceptanceRepository(uow)
            environment_repository = SQLAlchemyNetworkRuntimeEnvironmentRepository(uow)
            agent_gateway = NetworkAgentPromotionGateway(uow)
            use_case = AcceptNetworkExecutionUseCase(
                repository,
                agent_gateway,
                environment_repository,
                hard_max_depth=SETTINGS.network_max_depth_hard,
                hard_max_invocations=SETTINGS.network_max_invocations_hard,
                hard_timeout_seconds=SETTINGS.network_timeout_hard_seconds,
            )
            accepted = await use_case.execute(
                AcceptNetworkExecutionInput(
                    project_id=project_id,
                    network_id=network_id,
                    network_session_id=network_session_id,
                    message=message,
                    idempotency_key=idempotency_key,
                    expected_environment="production",
                    expected_network_version_id=network_version_id,
                )
            )

        return await self.get(
            run_id=accepted.id,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
        )

    async def get(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
    ) -> NetworkChatSurfaceRun:
        run = await self._observation.get_bound_run(
            run_id=run_id,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
            environment="production",
        )
        return self._view(run)

    async def find_active(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
    ) -> NetworkChatSurfaceRun | None:
        run = await self._observation.find_active_bound_run(
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
            environment="production",
        )
        return self._view(run) if run is not None else None

    async def find_latest(
        self,
        *,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
        created_after: datetime | None = None,
    ) -> NetworkChatSurfaceRun | None:
        run = await self._observation.find_latest_bound_run(
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
            created_after=created_after,
            environment="production",
        )
        return self._view(run) if run is not None else None

    async def cancel(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
    ) -> NetworkChatSurfaceRun:
        current = await self.get(
            run_id=run_id,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
        )
        async with NetworkUnitOfWork(DATABASE_ENGINE) as uow:
            repository = SQLAlchemyNetworkExecutionControlRepository(uow)
            runtime_control = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
            use_case = CancelNetworkExecutionUseCase(repository, runtime_control)
            result = await use_case.execute(
                CancelNetworkExecutionInput(
                    execution_id=run_id,
                    project_id=project_id,
                    expected_network_id=network_id,
                    expected_environment="production",
                )
            )
        if result.network_session_id != network_session_id:
            raise NotFoundError("Network execution not found")
        return NetworkChatSurfaceRun(
            id=current.id,
            project_id=current.project_id,
            network_id=current.network_id,
            network_session_id=current.network_session_id,
            network_version_id=current.network_version_id,
            environment=current.environment,
            status=result.status,
            input_message=current.input_message,
            created_at=current.created_at,
        )

    async def stream(
        self,
        *,
        run_id: UUID,
        project_id: UUID,
        network_id: UUID,
        network_session_id: UUID,
        network_version_id: UUID,
        is_disconnected=None,
    ) -> AsyncIterator[str]:
        async for chunk in self._observation.stream_bound_sse(
            run_id=run_id,
            project_id=project_id,
            network_id=network_id,
            network_session_id=network_session_id,
            network_version_id=network_version_id,
            environment="production",
            is_disconnected=is_disconnected,
        ):
            yield chunk


def build_network_chat_surface_runtime() -> NetworkChatSurfaceRuntime:
    return NetworkChatSurfaceRuntime()


__all__ = [
    "NetworkChatSurfaceRun",
    "NetworkChatSurfaceRuntime",
    "build_network_chat_surface_runtime",
]
