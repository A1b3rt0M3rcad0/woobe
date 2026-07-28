from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.application.promotion_aware_service import (
    NetworkApplicationService as PromotionAwareNetworkApplicationService,
)
from modules.network.domain.entities import NetworkDefinition
from modules.network.domain.enums import NetworkEnvironment
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkVersionModel
from shared.infra.errors import ConflictError, NotFoundError


_VALID_SESSION_MODES = {"stateful", "stateless"}


def _session_mode_value(value: Any) -> str | None:
    raw = getattr(value, "value", value)
    return str(raw) if raw in _VALID_SESSION_MODES else None


class NetworkApplicationService(PromotionAwareNetworkApplicationService):
    """Freezes each Agent Session Mode into executable Network bindings."""

    async def _resolve_draft_bindings(
        self,
        session: AsyncSession,
        definition: NetworkDefinition,
        project_id: UUID,
    ) -> dict[str, dict[str, Any]]:
        bindings = await super()._resolve_draft_bindings(
            session,
            definition,
            project_id,
        )
        for node_id, binding in bindings.items():
            snapshot = binding.get("snapshot_override")
            mode = _session_mode_value(
                snapshot.get("session_mode") if isinstance(snapshot, dict) else None
            )
            if mode is None:
                raise ConflictError(
                    f"Agent Draft snapshot has no valid Session Mode: {node_id}"
                )
            binding["session_mode"] = mode
        return bindings

    async def promote(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
        created_by: UUID | None,
        expected_revision: int | None = None,
        expected_network_version_id: UUID | None = None,
        approved_action_ids: list[str] | None = None,
    ) -> NetworkVersionModel:
        version = await super().promote(
            network_id=network_id,
            project_id=project_id,
            environment=environment,
            created_by=created_by,
            expected_revision=expected_revision,
            expected_network_version_id=expected_network_version_id,
            approved_action_ids=approved_action_ids,
        )
        return await self._freeze_version_session_modes(
            version_id=version.id,
            project_id=project_id,
        )

    async def rollback_production(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        target_version_id: UUID,
        created_by: UUID | None,
    ) -> NetworkVersionModel:
        version = await super().rollback_production(
            network_id=network_id,
            project_id=project_id,
            target_version_id=target_version_id,
            created_by=created_by,
        )
        return await self._freeze_version_session_modes(
            version_id=version.id,
            project_id=project_id,
        )

    async def _freeze_version_session_modes(
        self,
        *,
        version_id: UUID,
        project_id: UUID,
    ) -> NetworkVersionModel:
        async with self._session_factory() as session, session.begin():
            version = await session.get(
                NetworkVersionModel,
                version_id,
                with_for_update=True,
            )
            if version is None or version.project_id != project_id:
                raise NotFoundError("Network version not found")

            bindings = deepcopy(version.resolved_bindings or {})
            await self._freeze_bindings(
                session,
                project_id=project_id,
                bindings=bindings,
            )
            definition = self._definition(version.definition)
            version.resolved_bindings = bindings
            version.composition_hash = composition_hash(definition, bindings)
            await session.flush()
            return version

    @staticmethod
    async def _freeze_bindings(
        session: AsyncSession,
        *,
        project_id: UUID,
        bindings: dict[str, Any],
    ) -> None:
        parsed: dict[str, tuple[dict[str, Any], UUID, UUID]] = {}
        release_ids: set[UUID] = set()

        for node_id, raw_binding in bindings.items():
            if not isinstance(raw_binding, dict):
                raise ConflictError(
                    f"Invalid Agent binding for Network node: {node_id}"
                )

            raw_release_id = raw_binding.get("release_id")
            raw_agent_id = raw_binding.get("agent_id")
            try:
                release_id = UUID(str(raw_release_id))
                agent_id = UUID(str(raw_agent_id))
            except (TypeError, ValueError) as exc:
                raise ConflictError(
                    f"Network node has no valid immutable Agent binding: {node_id}"
                ) from exc

            parsed[node_id] = (raw_binding, release_id, agent_id)
            release_ids.add(release_id)

        if not parsed:
            return

        result = await session.execute(
            select(AgentReleaseModel).where(AgentReleaseModel.id.in_(release_ids))
        )
        releases = {release.id: release for release in result.scalars().all()}

        for node_id, (raw_binding, release_id, agent_id) in parsed.items():
            release = releases.get(release_id)
            if release is None:
                raise ConflictError(
                    f"Agent snapshot pinned by Network node was not found: {node_id}"
                )
            if release.project_id != project_id or release.agent_id != agent_id:
                raise ConflictError(
                    f"Agent snapshot does not belong to Network node: {node_id}"
                )

            mode = _session_mode_value(release.session_mode)
            if mode is None:
                raise ConflictError(
                    f"Agent snapshot has no valid Session Mode: {node_id}"
                )
            raw_binding["session_mode"] = mode


__all__ = ["NetworkApplicationService"]
