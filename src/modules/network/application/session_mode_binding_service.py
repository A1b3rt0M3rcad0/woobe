from __future__ import annotations

from copy import deepcopy
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
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
        agent_ids = {node.agent_id for node in definition.nodes}
        if not agent_ids:
            return {}

        agent_result = await session.execute(
            select(AgentModel).where(
                AgentModel.id.in_(agent_ids),
                AgentModel.project_id == project_id,
                AgentModel.status == "active",
            )
        )
        agents = {agent.id: agent for agent in agent_result.scalars().all()}

        missing_agent_ids = agent_ids - set(agents)
        if missing_agent_ids:
            missing = ", ".join(sorted(str(agent_id) for agent_id in missing_agent_ids))
            raise ConflictError(f"Agent Draft is unavailable: {missing}")

        ranked_drafts = (
            select(
                AgentReleaseModel.id.label("release_id"),
                func.row_number()
                .over(
                    partition_by=AgentReleaseModel.agent_id,
                    order_by=(
                        AgentReleaseModel.updated_at.desc(),
                        AgentReleaseModel.created_at.desc(),
                    ),
                )
                .label("row_number"),
            )
            .where(
                AgentReleaseModel.project_id == project_id,
                AgentReleaseModel.agent_id.in_(agent_ids),
                AgentReleaseModel.status == "draft",
            )
            .subquery()
        )
        draft_result = await session.execute(
            select(AgentReleaseModel)
            .join(
                ranked_drafts,
                AgentReleaseModel.id == ranked_drafts.c.release_id,
            )
            .where(ranked_drafts.c.row_number == 1)
        )
        draft_releases = {
            release.agent_id: release for release in draft_result.scalars().all()
        }

        bindings: dict[str, dict[str, Any]] = {}
        for node in definition.nodes:
            agent = agents[node.agent_id]
            draft_release = draft_releases.get(node.agent_id)
            agent_settings = dict(agent.settings or {})
            runtime_config = deepcopy(
                getattr(draft_release, "runtime_config", None)
                or agent_settings.get("runtime_config")
            )
            snapshot = {
                "system_prompt": (
                    draft_release.system_prompt
                    if draft_release is not None
                    and draft_release.system_prompt is not None
                    else agent.system_prompt
                ),
                "response_format": (
                    draft_release.response_format
                    if draft_release is not None
                    and draft_release.response_format is not None
                    else agent_settings.get("response_format")
                ),
                "provider": (
                    draft_release.provider
                    if draft_release is not None and draft_release.provider is not None
                    else agent.provider
                ),
                "model": (
                    draft_release.model
                    if draft_release is not None and draft_release.model is not None
                    else agent.model
                ),
                "provider_credential_id": self._uuid_text(
                    draft_release.provider_credential_id
                    if draft_release is not None
                    and draft_release.provider_credential_id is not None
                    else agent.provider_credential_id
                ),
                "provider_model_id": self._uuid_text(
                    getattr(draft_release, "provider_model_id", None)
                    or getattr(agent, "provider_model_id", None)
                ),
                "fallback_provider": (
                    draft_release.fallback_provider
                    if draft_release is not None
                    and draft_release.fallback_provider is not None
                    else agent.fallback_provider
                ),
                "fallback_model": (
                    draft_release.fallback_model
                    if draft_release is not None
                    and draft_release.fallback_model is not None
                    else agent.fallback_model
                ),
                "fallback_credential_id": self._uuid_text(
                    draft_release.fallback_credential_id
                    if draft_release is not None
                    and draft_release.fallback_credential_id is not None
                    else agent.fallback_credential_id
                ),
                "fallback_provider_model_id": self._uuid_text(
                    getattr(draft_release, "fallback_provider_model_id", None)
                    or getattr(agent, "fallback_provider_model_id", None)
                ),
                "temperature": (
                    draft_release.temperature
                    if draft_release is not None
                    and draft_release.temperature is not None
                    else agent.temperature
                ),
                "max_output_tokens": (
                    draft_release.max_output_tokens
                    if draft_release is not None
                    and draft_release.max_output_tokens is not None
                    else agent.max_output_tokens
                ),
                "session_mode": (
                    draft_release.session_mode
                    if draft_release is not None
                    and draft_release.session_mode is not None
                    else agent.session_mode
                ),
                "runtime_config": runtime_config,
            }
            mode = _session_mode_value(snapshot.get("session_mode"))
            if mode is None:
                raise ConflictError(
                    f"Agent Draft snapshot has no valid Session Mode: {node.id}"
                )

            bindings[str(node.id)] = {
                "node_id": str(node.id),
                "agent_id": str(node.agent_id),
                "draft_release_id": self._uuid_text(
                    draft_release.id if draft_release is not None else None
                ),
                "snapshot_override": snapshot,
                "session_mode": mode,
            }
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
