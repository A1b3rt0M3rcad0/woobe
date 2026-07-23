from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    KnowledgeVersionModel,
    ProviderCredentialModel,
)
from modules.agent.infra.database.provider_model_repositories import ProviderModelModel
from modules.agent.infra.database.vector_snapshot_models import VectorSnapshotModel
from modules.evaluation.infra.judge import canonical_hash
from modules.network.application import NetworkApplicationService
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from shared.infra.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.llm_cost import provider_model_pricing_snapshot


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
    runtime_config = release.runtime_config or {}
    rag_config = (
        runtime_config.get("rag")
        if isinstance(runtime_config.get("rag"), dict)
        else {}
    )
    return {
        "schema_version": 2,
        "agent_id": str(release.agent_id),
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
        "knowledge_version_id": _id_text(
            getattr(release, "knowledge_version_id", None)
        ),
        "vector_snapshot_id": _id_text(
            rag_config.get("vector_snapshot_id")
            or runtime_config.get("vector_snapshot_id")
        ),
        "collection_ids": [str(value) for value in (release.collection_ids or [])],
        "runtime_config": runtime_config,
        "release_id": str(release.id),
        "release_version": release.version,
        "snapshot_kind": release.snapshot_kind,
    }


class EvaluationTargetResolver:
    def __init__(self, session_factory: async_sessionmaker) -> None:
        self._session_factory = session_factory
        self._network_service = NetworkApplicationService(session_factory)

    @staticmethod
    def _validate_tool_snapshots(snapshot: dict[str, Any]) -> None:
        runtime_config = snapshot.get("runtime_config")
        if not isinstance(runtime_config, dict):
            return
        tools = runtime_config.get("tools")
        if not isinstance(tools, dict):
            return
        raw_ids = tools.get("tool_ids")
        if not isinstance(raw_ids, list) or not raw_ids:
            return
        snapshot_ids = {
            str(item.get("id"))
            for item in (tools.get("snapshots") or [])
            if isinstance(item, dict) and item.get("id") is not None
        }
        missing = sorted(
            str(raw_id) for raw_id in raw_ids if str(raw_id) not in snapshot_ids
        )
        if missing:
            raise ConflictError(
                "Evaluation target contains Tools without immutable snapshots: "
                + ", ".join(missing)
            )

    async def _seal_model_binding(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        snapshot: dict[str, Any],
        fallback: bool,
    ) -> None:
        prefix = "fallback_" if fallback else ""
        provider_model_key = f"{prefix}provider_model_id"
        credential_key = (
            "fallback_credential_id" if fallback else "provider_credential_id"
        )
        provider_key = f"{prefix}provider"
        model_key = f"{prefix}model"
        binding_key = "fallback_model_binding" if fallback else "model_binding"

        raw_values = {
            "provider_model_id": snapshot.get(provider_model_key),
            "provider_credential_id": snapshot.get(credential_key),
            "provider": snapshot.get(provider_key),
            "model": snapshot.get(model_key),
        }
        if fallback and not any(raw_values.values()):
            snapshot[binding_key] = None
            return
        if not all(raw_values.values()):
            role = "Fallback" if fallback else "Primary"
            raise ConflictError(
                f"{role} model binding is incomplete in the selected snapshot"
            )

        try:
            provider_model_id = UUID(str(raw_values["provider_model_id"]))
            credential_id = UUID(str(raw_values["provider_credential_id"]))
        except (TypeError, ValueError) as exc:
            raise ConflictError("Evaluation model binding contains invalid identifiers") from exc

        provider_model = await session.get(ProviderModelModel, provider_model_id)
        credential = await session.get(ProviderCredentialModel, credential_id)
        if (
            provider_model is None
            or provider_model.project_id != project_id
            or provider_model.status != "active"
        ):
            raise ConflictError(
                "Provider Model frozen by the selected snapshot is unavailable"
            )
        if (
            credential is None
            or credential.project_id != project_id
            or credential.status != "active"
        ):
            raise ConflictError(
                "Provider Credential frozen by the selected snapshot is unavailable"
            )
        if provider_model.provider_credential_id != credential.id:
            raise ConflictError(
                "Provider Model no longer points to the Credential frozen by the snapshot"
            )
        if provider_model.model != str(raw_values["model"]):
            raise ConflictError(
                "Provider Model slug differs from the value frozen by the snapshot"
            )
        if credential.provider != str(raw_values["provider"]):
            raise ConflictError(
                "Provider differs from the value frozen by the selected snapshot"
            )

        metadata = deepcopy(provider_model.meta or {})
        pricing = provider_model_pricing_snapshot(
            provider_model_id=provider_model.id,
            provider_credential_id=credential.id,
            provider=credential.provider,
            model=provider_model.model,
            metadata=metadata,
        )
        snapshot[binding_key] = {
            "provider_model_id": str(provider_model.id),
            "provider_credential_id": str(credential.id),
            "provider": credential.provider,
            "model": provider_model.model,
            "provider_model_status": provider_model.status,
            "credential_status": credential.status,
            "model_metadata": metadata,
            "pricing_snapshot": pricing,
        }

    async def _seal_agent_snapshot(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        sealed = deepcopy(snapshot)
        if sealed.get("session_mode") not in {"stateful", "stateless"}:
            raise ConflictError(
                "Evaluation target snapshot has no valid Session Mode"
            )
        await self._seal_model_binding(
            session,
            project_id=project_id,
            snapshot=sealed,
            fallback=False,
        )
        await self._seal_model_binding(
            session,
            project_id=project_id,
            snapshot=sealed,
            fallback=True,
        )
        await self._seal_rag_binding(
            session,
            project_id=project_id,
            snapshot=sealed,
        )
        self._validate_tool_snapshots(sealed)
        sealed["binding_mode"] = "frozen_snapshot"
        sealed["snapshot_schema_version"] = max(
            int(sealed.get("schema_version") or 1),
            2,
        )
        return sealed

    async def _seal_rag_binding(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        snapshot: dict[str, Any],
    ) -> None:
        raw_knowledge_id = snapshot.get("knowledge_version_id")
        if not raw_knowledge_id:
            snapshot["rag_embedding_binding"] = None
            return
        try:
            knowledge_id = UUID(str(raw_knowledge_id))
            agent_id = UUID(str(snapshot.get("agent_id")))
        except (TypeError, ValueError) as exc:
            raise ConflictError(
                "Evaluation Knowledge binding contains invalid identifiers"
            ) from exc

        knowledge = await session.get(KnowledgeVersionModel, knowledge_id)
        if (
            knowledge is None
            or knowledge.project_id != project_id
            or knowledge.agent_id != agent_id
        ):
            raise ConflictError(
                "KnowledgeVersion frozen by the selected snapshot is unavailable"
            )
        knowledge_metadata = (
            knowledge.snapshot_metadata
            if isinstance(knowledge.snapshot_metadata, dict)
            else {}
        )
        raw_vector_id = knowledge_metadata.get("vector_snapshot_id")
        if not raw_vector_id:
            raise ConflictError(
                "KnowledgeVersion frozen by the snapshot has no Vector Snapshot"
            )
        try:
            vector_id = UUID(str(raw_vector_id))
        except (TypeError, ValueError) as exc:
            raise ConflictError("Vector Snapshot identifier is invalid") from exc

        vector = await session.get(VectorSnapshotModel, vector_id)
        if (
            vector is None
            or vector.project_id != project_id
            or vector.status != "READY"
            or not vector.snapshot_hash
        ):
            raise ConflictError(
                "Vector Snapshot frozen by the Evaluation target is not READY"
            )
        provider_model = await session.get(
            ProviderModelModel,
            vector.embedding_provider_model_id,
        )
        if (
            provider_model is None
            or provider_model.project_id != project_id
            or provider_model.status != "active"
        ):
            raise ConflictError(
                "Embedding Provider Model frozen by the Vector Snapshot is unavailable"
            )
        credential = await session.get(
            ProviderCredentialModel,
            provider_model.provider_credential_id,
        )
        if (
            credential is None
            or credential.project_id != project_id
            or credential.status != "active"
        ):
            raise ConflictError(
                "Embedding Credential frozen by the Vector Snapshot is unavailable"
            )
        if (
            provider_model.model != vector.embedding_model
            or credential.provider != vector.embedding_provider
        ):
            raise ConflictError(
                "Embedding binding drifted from the immutable Vector Snapshot"
            )

        model_metadata = deepcopy(provider_model.meta or {})
        credential_metadata = deepcopy(credential.meta or {})
        snapshot["vector_snapshot_id"] = str(vector.id)
        snapshot["rag_embedding_binding"] = {
            "knowledge_version_id": str(knowledge.id),
            "vector_snapshot_id": str(vector.id),
            "vector_snapshot_hash": vector.snapshot_hash,
            "provider_model_id": str(provider_model.id),
            "provider_credential_id": str(credential.id),
            "provider": vector.embedding_provider,
            "model": vector.embedding_model,
            "dimensions": vector.embedding_dimensions,
            "base_url": (
                model_metadata.get("base_url")
                or credential_metadata.get("base_url")
            ),
        }

    async def _seal_network_bindings(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        bindings: dict[str, Any],
    ) -> dict[str, Any]:
        sealed_bindings = deepcopy(bindings)
        for node_id, binding in sealed_bindings.items():
            if not isinstance(binding, dict):
                raise ConflictError(f"Invalid Agent binding for Network node: {node_id}")
            raw_agent_id = binding.get("agent_id")
            try:
                agent_id = UUID(str(raw_agent_id))
            except (TypeError, ValueError) as exc:
                raise ConflictError(
                    f"Network node has no valid Agent binding: {node_id}"
                ) from exc

            raw_release_id = binding.get("release_id") or binding.get(
                "draft_release_id"
            )
            release = None
            if raw_release_id:
                try:
                    release = await session.get(
                        AgentReleaseModel,
                        UUID(str(raw_release_id)),
                    )
                except (TypeError, ValueError) as exc:
                    raise ConflictError(
                        f"Network node has an invalid Agent snapshot id: {node_id}"
                    ) from exc
                if (
                    release is None
                    or release.project_id != project_id
                    or release.agent_id != agent_id
                ):
                    raise ConflictError(
                        f"Agent snapshot does not belong to Network node: {node_id}"
                    )

            raw_snapshot = (
                _agent_release_snapshot(release)
                if release is not None
                else binding.get("snapshot_override")
            )
            if not isinstance(raw_snapshot, dict):
                raise ConflictError(
                    f"Network node has no executable frozen snapshot: {node_id}"
                )
            raw_snapshot = deepcopy(raw_snapshot)
            raw_snapshot["agent_id"] = str(agent_id)
            sealed = await self._seal_agent_snapshot(
                session,
                project_id=project_id,
                snapshot=raw_snapshot,
            )
            binding["snapshot_override"] = sealed
            binding["binding_mode"] = "frozen_snapshot"
            binding["session_mode"] = sealed.get("session_mode")
        return sealed_bindings

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
            if release_id is not None:
                release = await session.get(AgentReleaseModel, release_id)
                if (
                    release is None
                    or release.project_id != project_id
                    or release.agent_id != agent_id
                    or release.status != "staging"
                ):
                    raise NotFoundError("Agent Staging version not found")
            else:
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

        snapshot = await self._seal_agent_snapshot(
            session,
            project_id=project_id,
            snapshot=_agent_release_snapshot(release),
        )
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
            display_version="Current Draft" if source_type == "draft" else release.version,
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
            bindings = await self._seal_network_bindings(
                session,
                project_id=project_id,
                bindings=bindings,
            )
            resolved_composition_hash = composition_hash(definition, bindings)
            snapshot = {
                "schema_version": 1,
                "draft_revision": network.draft_revision,
                "definition": definition.to_dict(),
                "resolved_bindings": bindings,
                "composition_hash": resolved_composition_hash,
                "timeout_seconds": definition.limits.timeout_seconds,
                "binding_mode": "frozen_snapshot",
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
            environment = (
                "production"
                if selected_version_id == network.production_version_id
                else "release"
            )
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
        definition = self._network_service._definition(version.definition)
        bindings = await self._seal_network_bindings(
            session,
            project_id=project_id,
            bindings=version.resolved_bindings,
        )
        resolved_composition_hash = composition_hash(definition, bindings)
        snapshot = {
            "schema_version": 1,
            "network_version_id": str(version.id),
            "version": version.version,
            "kind": version.kind,
            "definition": version.definition,
            "resolved_bindings": bindings,
            "composition_hash": resolved_composition_hash,
            "timeout_seconds": definition.limits.timeout_seconds,
            "binding_mode": "frozen_snapshot",
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
            composition_hash=resolved_composition_hash,
            display_name=network.name,
            display_version=version.version,
        )
