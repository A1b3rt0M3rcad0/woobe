from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.evaluation.infra.judge import canonical_hash
from modules.network.application import NetworkApplicationService
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from shared.infra.errors import ConflictError, NotFoundError, ValidationError


@dataclass(frozen=True)
class ResolvedEvaluationTarget:
    target_type: str
    source_type: str
    entity_id: UUID
    environment: str
    agent_release_id: UUID | None
    network_version_id: UUID | None
    snapshot: dict[str, Any]
    snapshot_hash: str
    composition_hash: str | None
    display_name: str
    display_version: str


def _id_text(value: Any) -> str | None:
    return str(value) if value else None


def _agent_release_snapshot(release: AgentReleaseModel) -> dict[str, Any]:
    return {
        "name": release.name,
        "description": release.description,
        "system_prompt": release.system_prompt,
        "response_format": release.response_format,
        "output_schema": release.output_schema,
        "provider": release.provider,
        "model": release.model,
        "provider_credential_id": _id_text(release.provider_credential_id),
        "provider_model_id": _id_text(getattr(release, "provider_model_id", None)),
        "fallback_provider": release.fallback_provider,
        "fallback_model": release.fallback_model,
        "fallback_credential_id": _id_text(release.fallback_credential_id),
        "fallback_provider_model_id": _id_text(
            getattr(release, "fallback_provider_model_id", None)
        ),
        "base_url": release.base_url,
        "temperature": release.temperature,
        "max_output_tokens": release.max_output_tokens,
        "session_mode": release.session_mode,
        "agent_status": release.agent_status,
        "collection_ids": [str(value) for value in (release.collection_ids or [])],
        "runtime_config": release.runtime_config or {},
        "release_id": str(release.id),
        "release_version": release.version,
        "snapshot_kind": release.snapshot_kind,
    }


class EvaluationTargetResolver:
    def __init__(
        self,
        session_factory: async_sessionmaker,
    ) -> None:
        self._session_factory = session_factory
        self._network_service = NetworkApplicationService(session_factory)

    async def resolve(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        target_type: str,
        source_type: str,
        entity_id: UUID,
        version_id: UUID | None = None,
    ) -> ResolvedEvaluationTarget:
        if target_type == "agent":
            return await self._resolve_agent(
                session,
                project_id=project_id,
                source_type=source_type,
                agent_id=entity_id,
                release_id=version_id,
            )
        if target_type == "network":
            return await self._resolve_network(
                session,
                project_id=project_id,
                source_type=source_type,
                network_id=entity_id,
                version_id=version_id,
            )
        raise ValidationError("Evaluation target_type must be agent or network")

    async def _resolve_agent(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        source_type: str,
        agent_id: UUID,
        release_id: UUID | None,
    ) -> ResolvedEvaluationTarget:
        agent = await session.get(AgentModel, agent_id)
        if agent is None or agent.project_id != project_id:
            raise NotFoundError("Agent not found")

        if source_type == "draft":
            release = await session.scalar(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.agent_id == agent_id,
                    AgentReleaseModel.status == "draft",
                )
                .order_by(
                    AgentReleaseModel.updated_at.desc(),
                    AgentReleaseModel.created_at.desc(),
                )
                .limit(1)
            )
            if release is None:
                raise ConflictError("Save the Agent Draft before evaluating it")
            environment = "draft"
        elif source_type == "staging":
            release = await session.scalar(
                select(AgentReleaseModel)
                .where(
                    AgentReleaseModel.project_id == project_id,
                    AgentReleaseModel.agent_id == agent_id,
                    AgentReleaseModel.status == "staging",
                )
                .order_by(AgentReleaseModel.created_at.desc())
                .limit(1)
            )
            if release is None:
                raise ConflictError("Agent Staging is not ready")
            environment = "staging"
        elif source_type == "release":
            if release_id is not None:
                release = await session.get(AgentReleaseModel, release_id)
                if (
                    release is None
                    or release.project_id != project_id
                    or release.agent_id != agent_id
                    or release.snapshot_kind != "release"
                ):
                    raise NotFoundError("Agent Release not found")
            else:
                release = await session.scalar(
                    select(AgentReleaseModel)
                    .where(
                        AgentReleaseModel.project_id == project_id,
                        AgentReleaseModel.agent_id == agent_id,
                        AgentReleaseModel.status == "production",
                        AgentReleaseModel.snapshot_kind == "release",
                    )
                    .order_by(AgentReleaseModel.created_at.desc())
                    .limit(1)
                )
                if release is None:
                    raise ConflictError("Agent Production is not ready")
            environment = "production" if release.status == "production" else "release"
        else:
            raise ValidationError("Agent source_type must be draft, staging or release")

        snapshot = _agent_release_snapshot(release)
        return ResolvedEvaluationTarget(
            target_type="agent",
            source_type=source_type,
            entity_id=agent_id,
            environment=environment,
            agent_release_id=release.id if source_type != "draft" else None,
            network_version_id=None,
            snapshot=snapshot,
            snapshot_hash=canonical_hash(snapshot),
            composition_hash=None,
            display_name=agent.name,
            display_version=(
                "Current Draft"
                if source_type == "draft"
                else release.version
            ),
        )

    async def _resolve_network(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        source_type: str,
        network_id: UUID,
        version_id: UUID | None,
    ) -> ResolvedEvaluationTarget:
        network = await session.get(NetworkModel, network_id)
        if network is None or network.project_id != project_id:
            raise NotFoundError("Network not found")

        if source_type == "draft":
            definition = self._network_service._definition(network.draft_definition)
            bindings = await self._network_service._resolve_draft_bindings(
                session,
                definition,
                project_id,
            )
            from modules.network.domain.graph import composition_hash

            resolved_composition_hash = composition_hash(definition, bindings)
            snapshot = {
                "draft_revision": network.draft_revision,
                "definition": definition.to_dict(),
                "resolved_bindings": bindings,
                "composition_hash": resolved_composition_hash,
            }
            return ResolvedEvaluationTarget(
                target_type="network",
                source_type="draft",
                entity_id=network_id,
                environment="draft",
                agent_release_id=None,
                network_version_id=None,
                snapshot=snapshot,
                snapshot_hash=canonical_hash(snapshot),
                composition_hash=resolved_composition_hash,
                display_name=network.name,
                display_version=f"Draft r{network.draft_revision}",
            )

        if source_type == "staging":
            selected_version_id = version_id or network.staging_version_id
            expected_kind = "staging"
            environment = "staging"
        elif source_type == "release":
            selected_version_id = version_id or network.production_version_id
            expected_kind = "release"
            environment = "production" if selected_version_id == network.production_version_id else "release"
        else:
            raise ValidationError("Network source_type must be draft, staging or release")

        if selected_version_id is None:
            raise ConflictError(f"Network {source_type.title()} is not ready")
        version = await session.get(NetworkVersionModel, selected_version_id)
        if (
            version is None
            or version.project_id != project_id
            or version.network_id != network_id
            or version.kind != expected_kind
        ):
            raise NotFoundError(f"Network {source_type.title()} version not found")
        snapshot = {
            "network_version_id": str(version.id),
            "version": version.version,
            "kind": version.kind,
            "definition": version.definition,
            "resolved_bindings": version.resolved_bindings,
            "composition_hash": version.composition_hash,
        }
        return ResolvedEvaluationTarget(
            target_type="network",
            source_type=source_type,
            entity_id=network_id,
            environment=environment,
            agent_release_id=None,
            network_version_id=version.id,
            snapshot=snapshot,
            snapshot_hash=canonical_hash(snapshot),
            composition_hash=version.composition_hash,
            display_name=network.name,
            display_version=version.version,
        )
