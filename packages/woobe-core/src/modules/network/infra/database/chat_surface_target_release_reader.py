from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from shared.contracts.errors import ConflictError, NotFoundError
from shared.runtime_environment import assert_runtime_environment_enabled


@dataclass(frozen=True, slots=True)
class NetworkChatSurfaceTargetRelease:
    id: UUID
    version: str


class NetworkChatSurfaceTargetReleaseReader:
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    async def current(
        self,
        *,
        project_id: UUID,
        target_id: UUID,
    ) -> NetworkChatSurfaceTargetRelease:
        async with self._uow:
            session = self._uow.session
            target = await session.get(NetworkModel, target_id)
            if target is None or target.project_id != project_id:
                raise NotFoundError("Network not found")

            await assert_runtime_environment_enabled(
                session,
                target_type="network",
                target_id=target_id,
                project_id=project_id,
                environment="production",
            )

            release_id = target.production_version_id
            if release_id is None:
                raise ConflictError("Network Production is not ready")
            release = await session.get(NetworkVersionModel, release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.network_id != target_id
                or release.kind != "release"
            ):
                raise ConflictError("Network Production release was not found")
            return NetworkChatSurfaceTargetRelease(
                id=release.id,
                version=release.version,
            )

    async def validate(
        self,
        *,
        project_id: UUID,
        target_id: UUID,
        release_id: UUID,
    ) -> NetworkChatSurfaceTargetRelease:
        async with self._uow:
            session = self._uow.session
            await assert_runtime_environment_enabled(
                session,
                target_type="network",
                target_id=target_id,
                project_id=project_id,
                environment="production",
            )
            release = await session.get(NetworkVersionModel, release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.network_id != target_id
                or release.kind != "release"
            ):
                raise ConflictError("Pinned Network Release is unavailable")
            return NetworkChatSurfaceTargetRelease(
                id=release.id,
                version=release.version,
            )


__all__ = [
    "NetworkChatSurfaceTargetRelease",
    "NetworkChatSurfaceTargetReleaseReader",
]
