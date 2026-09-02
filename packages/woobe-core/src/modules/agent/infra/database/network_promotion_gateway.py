from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.application.use_cases.network_snapshot_lifecycle import (
    NetworkAgentSnapshotLifecycle,
)
from modules.agent.domain.entities import AgentRelease
from modules.agent.domain.release_snapshot import (
    release_snapshot_hash,
    release_snapshots_equal,
)
from modules.agent.infra.database.mappers import agent_release_model_to_entity
from modules.agent.infra.database.models import AgentModel, AgentReleaseModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository


_VALID_SESSION_MODES = {"stateful", "stateless"}


class _SessionOwner(Protocol):
    @property
    def session(self) -> AsyncSession: ...


class NetworkAgentPromotionGateway:
    """Agent persistence boundary shared with one caller-owned SQL transaction."""

    def __init__(self, transaction: _SessionOwner) -> None:
        self._transaction = transaction

    @property
    def _session(self) -> AsyncSession:
        return self._transaction.session

    async def is_active_agent(self, *, project_id: UUID, agent_id: UUID) -> bool:
        value = await self._session.scalar(
            select(AgentModel.id).where(
                AgentModel.id == agent_id,
                AgentModel.project_id == project_id,
                AgentModel.status == "active",
            )
        )
        return value is not None

    async def latest_draft(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        statement = (
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.project_id == project_id,
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.status == "draft",
                AgentReleaseModel.snapshot_kind == "draft",
            )
            .order_by(
                AgentReleaseModel.updated_at.desc(),
                AgentReleaseModel.created_at.desc(),
            )
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        return agent_release_model_to_entity(model) if model is not None else None

    async def snapshot_by_id(
        self,
        *,
        release_id: UUID | None,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        if release_id is None:
            return None
        statement = select(AgentReleaseModel).where(
            AgentReleaseModel.id == release_id,
            AgentReleaseModel.project_id == project_id,
            AgentReleaseModel.agent_id == agent_id,
        )
        if lock:
            statement = statement.with_for_update()
        model = await self._session.scalar(statement)
        return agent_release_model_to_entity(model) if model is not None else None

    async def equivalent_snapshot(
        self,
        *,
        source: AgentRelease,
        target_kind: str,
        active_only: bool,
        lock: bool,
    ) -> AgentRelease | None:
        statement = select(AgentReleaseModel).where(
            AgentReleaseModel.project_id == source.project_id,
            AgentReleaseModel.agent_id == source.agent_id,
            AgentReleaseModel.snapshot_kind == target_kind,
            AgentReleaseModel.id != source.id,
        )
        if active_only:
            statement = statement.where(AgentReleaseModel.status == target_kind)
        statement = statement.order_by(AgentReleaseModel.created_at.desc())
        if lock:
            statement = statement.with_for_update()
        result = await self._session.scalars(statement)
        for model in result.all():
            candidate = agent_release_model_to_entity(model)
            if release_snapshots_equal(candidate, source):
                return candidate
        return None

    async def promote_draft_to_staging(
        self,
        source: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> AgentRelease:
        repository = SQLAlchemyAgentReleaseRepository(self._session)  # type: ignore[arg-type]
        lifecycle = NetworkAgentSnapshotLifecycle(repository)
        resolution = await lifecycle.promote_draft_to_staging(source, user_id=user_id)
        return resolution.release

    async def publish_staging_for_network(
        self,
        source: AgentRelease,
        *,
        user_id: UUID | None,
    ) -> AgentRelease:
        repository = SQLAlchemyAgentReleaseRepository(self._session)  # type: ignore[arg-type]
        lifecycle = NetworkAgentSnapshotLifecycle(repository)
        resolution = await lifecycle.publish_staging_for_network(source, user_id=user_id)
        return resolution.release

    async def resolve_runtime_bindings(
        self,
        *,
        project_id: UUID,
        nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]:
        """Freeze Agent state for a Draft Network execution inside caller transaction."""

        agent_ids = {UUID(str(item["agent_id"])) for item in nodes}
        if not agent_ids:
            return {}

        agents_result = await self._session.scalars(
            select(AgentModel).where(
                AgentModel.id.in_(agent_ids),
                AgentModel.project_id == project_id,
                AgentModel.status == "active",
            )
        )
        agents = {agent.id: agent for agent in agents_result.all()}
        missing = agent_ids - set(agents)
        if missing:
            values = ", ".join(sorted(str(agent_id) for agent_id in missing))
            raise ValueError(f"Agent Draft is unavailable: {values}")

        bindings: dict[str, dict[str, Any]] = {}
        for item in nodes:
            node_id = UUID(str(item["node_id"]))
            agent_id = UUID(str(item["agent_id"]))
            source = str(item.get("binding_source") or "draft")
            raw_release_id = item.get("release_id")
            agent = agents[agent_id]

            if source != "draft":
                release_id = UUID(str(raw_release_id)) if raw_release_id else None
                release = await self.snapshot_by_id(
                    release_id=release_id,
                    project_id=project_id,
                    agent_id=agent_id,
                    lock=False,
                )
                if release is None or release.snapshot_kind != source:
                    raise ValueError(f"Pinned Agent snapshot is unavailable: {agent_id}")
                mode = _session_mode(release.session_mode)
                if mode is None:
                    raise ValueError(
                        f"Agent snapshot has no valid Session Mode: {node_id}"
                    )
                bindings[str(node_id)] = {
                    "node_id": str(node_id),
                    "agent_id": str(agent_id),
                    "binding_source": source,
                    "release_id": str(release.id),
                    "release_version": release.version,
                    "release_status": _enum_value(release.status),
                    "snapshot_kind": release.snapshot_kind,
                    "snapshot_hash": release_snapshot_hash(release),
                    "session_mode": mode,
                }
                continue

            draft_release = await self._latest_draft_model(
                project_id=project_id,
                agent_id=agent_id,
            )
            agent_settings = dict(agent.settings or {})
            runtime_config = deepcopy(
                getattr(draft_release, "runtime_config", None)
                or agent_settings.get("runtime_config")
            )
            snapshot = {
                "system_prompt": _prefer(draft_release, "system_prompt", agent.system_prompt),
                "response_format": _prefer(
                    draft_release,
                    "response_format",
                    agent_settings.get("response_format"),
                ),
                "provider": _prefer(draft_release, "provider", agent.provider),
                "model": _prefer(draft_release, "model", agent.model),
                "provider_credential_id": _uuid_text(
                    _prefer(
                        draft_release,
                        "provider_credential_id",
                        agent.provider_credential_id,
                    )
                ),
                "provider_model_id": _uuid_text(
                    getattr(draft_release, "provider_model_id", None)
                    or getattr(agent, "provider_model_id", None)
                ),
                "fallback_provider": _prefer(
                    draft_release,
                    "fallback_provider",
                    agent.fallback_provider,
                ),
                "fallback_model": _prefer(
                    draft_release,
                    "fallback_model",
                    agent.fallback_model,
                ),
                "fallback_credential_id": _uuid_text(
                    _prefer(
                        draft_release,
                        "fallback_credential_id",
                        agent.fallback_credential_id,
                    )
                ),
                "fallback_provider_model_id": _uuid_text(
                    getattr(draft_release, "fallback_provider_model_id", None)
                    or getattr(agent, "fallback_provider_model_id", None)
                ),
                "temperature": _prefer(
                    draft_release,
                    "temperature",
                    agent.temperature,
                ),
                "max_output_tokens": _prefer(
                    draft_release,
                    "max_output_tokens",
                    agent.max_output_tokens,
                ),
                "session_mode": _prefer(
                    draft_release,
                    "session_mode",
                    agent.session_mode,
                ),
                "runtime_config": runtime_config,
            }
            mode = _session_mode(snapshot["session_mode"])
            if mode is None:
                raise ValueError(
                    f"Agent Draft snapshot has no valid Session Mode: {node_id}"
                )
            snapshot["session_mode"] = mode
            bindings[str(node_id)] = {
                "node_id": str(node_id),
                "agent_id": str(agent_id),
                "binding_source": "draft",
                "draft_release_id": _uuid_text(
                    draft_release.id if draft_release is not None else None
                ),
                "snapshot_override": snapshot,
                "snapshot_hash": _canonical_hash(snapshot),
                "session_mode": mode,
            }
        return bindings

    async def _latest_draft_model(
        self,
        *,
        project_id: UUID,
        agent_id: UUID,
    ) -> AgentReleaseModel | None:
        return await self._session.scalar(
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

    @staticmethod
    def snapshot_hash(snapshot: AgentRelease) -> str:
        return release_snapshot_hash(snapshot)

    @staticmethod
    def snapshots_equal(left: AgentRelease, right: AgentRelease) -> bool:
        return release_snapshots_equal(left, right)


def _prefer(source: Any, field: str, fallback: Any) -> Any:
    value = getattr(source, field, None) if source is not None else None
    return value if value is not None else fallback


def _uuid_text(value: Any) -> str | None:
    return str(value) if value else None


def _enum_value(value: Any) -> str:
    return str(getattr(value, "value", value))


def _session_mode(value: Any) -> str | None:
    normalized = _enum_value(value)
    return normalized if normalized in _VALID_SESSION_MODES else None


def _canonical_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
