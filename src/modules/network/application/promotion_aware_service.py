from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
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
from modules.agent.infra.database.models import AgentReleaseModel
from modules.agent.infra.database.repositories import SQLAlchemyAgentReleaseRepository
from modules.network.application.service_core import (
    NetworkApplicationService as CoreNetworkApplicationService,
)
from modules.network.domain.entities import NetworkDefinition, NetworkNode
from modules.network.domain.enums import NetworkEnvironment, NetworkVersionKind
from modules.network.domain.graph import composition_hash
from modules.network.infra.database.models import NetworkModel, NetworkVersionModel
from modules.network.infra.database.repositories import NetworkRepository
from shared.infra.errors import ConflictError, NotFoundError


@dataclass
class _NodePlan:
    node: NetworkNode
    selected_source: str
    selected_release: AgentRelease | None
    result_source: str
    result_release: AgentRelease | None
    action_required: str | None = None
    action_id: str | None = None
    blocking_reason: str | None = None
    reuse_reason: str | None = None
    result_resolution: str = "retained"

    @property
    def snapshot_hash(self) -> str | None:
        release = self.selected_release or self.result_release
        return release_snapshot_hash(release) if release is not None else None


class NetworkApplicationService(CoreNetworkApplicationService):
    """Network service with deterministic Agent snapshot promotion."""

    async def preview_promotion(
        self,
        *,
        network_id: UUID,
        project_id: UUID,
        environment: NetworkEnvironment,
    ) -> dict[str, Any]:
        async with self._session_factory() as session:
            network = await NetworkRepository(session).get(network_id)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")
            definition, source_version, plans = await self._plan_promotion(
                session,
                network=network,
                project_id=project_id,
                environment=environment,
                lock=False,
            )
            return self._preview_payload(
                network=network,
                environment=environment,
                source_version=source_version,
                definition=definition,
                plans=plans,
            )

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
        async with self._session_factory() as session, session.begin():
            network = await session.get(NetworkModel, network_id, with_for_update=True)
            if network is None or network.project_id != project_id:
                raise NotFoundError("Network not found")

            if (
                environment == NetworkEnvironment.STAGING
                and expected_revision is not None
                and expected_revision != network.draft_revision
            ):
                raise ConflictError(
                    "Network Draft changed after the promotion preview. Review the updated plan before staging."
                )
            if (
                environment == NetworkEnvironment.PRODUCTION
                and expected_network_version_id is not None
                and expected_network_version_id != network.staging_version_id
            ):
                raise ConflictError(
                    "Network Staging changed after the promotion preview. Review the updated plan before publishing."
                )

            definition, source_version, plans = await self._plan_promotion(
                session,
                network=network,
                project_id=project_id,
                environment=environment,
                lock=True,
            )
            blocked = [plan for plan in plans if plan.blocking_reason]
            if blocked:
                raise ConflictError(blocked[0].blocking_reason or "Network promotion is blocked")

            required_ids = {
                plan.action_id for plan in plans if plan.action_id is not None
            }
            approved_ids = set(approved_action_ids or [])
            if not required_ids.issubset(approved_ids):
                if environment == NetworkEnvironment.STAGING:
                    raise ConflictError(
                        "An Agent Draft changed after the promotion preview. Review the updated plan before staging the Network."
                    )
                raise ConflictError(
                    "An Agent Staging snapshot changed after the promotion preview. Review the updated plan before publishing the Network."
                )

            release_repo = SQLAlchemyAgentReleaseRepository(session)
            lifecycle = NetworkAgentSnapshotLifecycle(release_repo)
            action_results: dict[str, AgentRelease] = {}
            for plan in plans:
                if plan.action_id is None or plan.action_id in action_results:
                    continue
                if plan.selected_release is None:
                    raise ConflictError("Agent snapshot selected for promotion was not found")
                if plan.action_required == "promote_draft_to_staging":
                    resolution = await lifecycle.promote_draft_to_staging(
                        plan.selected_release,
                        user_id=created_by,
                    )
                elif plan.action_required == "publish_staging_to_release":
                    resolution = await lifecycle.publish_staging_for_network(
                        plan.selected_release,
                        user_id=created_by,
                    )
                else:
                    continue
                action_results[plan.action_id] = resolution.release

            bindings: dict[str, dict[str, Any]] = {}
            for plan in plans:
                result = (
                    action_results.get(plan.action_id)
                    if plan.action_id is not None
                    else plan.result_release
                )
                if result is None:
                    raise ConflictError(
                        f"Agent snapshot could not be resolved: {plan.node.agent_id}"
                    )
                snapshot_kind = getattr(result, "snapshot_kind", None)
                binding_source = "release" if snapshot_kind == "release" else "staging"
                bindings[str(plan.node.id)] = {
                    "node_id": str(plan.node.id),
                    "agent_id": str(plan.node.agent_id),
                    "binding_source": binding_source,
                    "release_id": str(result.id),
                    "release_version": result.version,
                    "release_status": getattr(result.status, "value", result.status),
                    "snapshot_kind": snapshot_kind,
                    "snapshot_hash": release_snapshot_hash(result),
                }

            kind = (
                NetworkVersionKind.STAGING
                if environment == NetworkEnvironment.STAGING
                else NetworkVersionKind.RELEASE
            )
            count = await session.scalar(
                select(func.count(NetworkVersionModel.id)).where(
                    NetworkVersionModel.network_id == network.id,
                    NetworkVersionModel.kind == kind.value,
                )
            )
            now = datetime.now(timezone.utc)
            version = NetworkVersionModel(
                network_id=network.id,
                project_id=project_id,
                kind=kind.value,
                version=f"v{int(count or 0) + 1}.{now:%Y%m%d.%H%M%S}",
                definition=definition.to_dict(),
                resolved_bindings=bindings,
                composition_hash=composition_hash(definition, bindings),
                created_by=created_by,
            )
            session.add(version)
            await session.flush()
            if environment == NetworkEnvironment.STAGING:
                network.staging_version_id = version.id
            else:
                network.production_version_id = version.id
            return version

    async def _plan_promotion(
        self,
        session: AsyncSession,
        *,
        network: NetworkModel,
        project_id: UUID,
        environment: NetworkEnvironment,
        lock: bool,
    ) -> tuple[NetworkDefinition, NetworkVersionModel | None, list[_NodePlan]]:
        if environment == NetworkEnvironment.STAGING:
            definition = self._definition(network.draft_definition)
            plans = await self._plan_staging_nodes(
                session,
                definition=definition,
                project_id=project_id,
                lock=lock,
            )
            return definition, None, plans

        if network.staging_version_id is None:
            raise ConflictError("Stage the Network before publishing Production")
        source_version = await session.get(
            NetworkVersionModel,
            network.staging_version_id,
            with_for_update=lock,
        )
        if (
            source_version is None
            or source_version.network_id != network.id
            or source_version.kind != NetworkVersionKind.STAGING.value
        ):
            raise ConflictError("Current Network Staging version was not found")
        definition = self._definition(source_version.definition)
        plans = await self._plan_release_nodes(
            session,
            definition=definition,
            resolved_bindings=source_version.resolved_bindings or {},
            project_id=project_id,
            lock=lock,
        )
        return definition, source_version, plans

    async def _plan_staging_nodes(
        self,
        session: AsyncSession,
        *,
        definition: NetworkDefinition,
        project_id: UUID,
        lock: bool,
    ) -> list[_NodePlan]:
        plans: list[_NodePlan] = []
        for node in definition.nodes:
            if node.binding.source == "draft":
                draft = await self._latest_by_status(
                    session,
                    project_id=project_id,
                    agent_id=node.agent_id,
                    status="draft",
                    lock=lock,
                )
                if draft is None:
                    plans.append(
                        _NodePlan(
                            node=node,
                            selected_source="draft",
                            selected_release=None,
                            result_source="staging",
                            result_release=None,
                            blocking_reason="Agent Draft is unavailable. Save the Agent Draft before staging the Network.",
                            result_resolution="blocked",
                        )
                    )
                    continue
                staging = await self._latest_by_status(
                    session,
                    project_id=project_id,
                    agent_id=node.agent_id,
                    status="staging",
                    lock=lock,
                )
                if staging is not None and release_snapshots_equal(draft, staging):
                    plans.append(
                        _NodePlan(
                            node=node,
                            selected_source="draft",
                            selected_release=draft,
                            result_source="staging",
                            result_release=staging,
                            reuse_reason="Current Agent Staging already matches the saved Draft.",
                            result_resolution="equivalent_reused",
                        )
                    )
                    continue
                action_id = self._action_id("stage", draft)
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="draft",
                        selected_release=draft,
                        result_source="staging",
                        result_release=None,
                        action_required="promote_draft_to_staging",
                        action_id=action_id,
                        result_resolution="promoted",
                    )
                )
                continue

            exact = await self._exact_binding_release(
                session,
                node=node,
                project_id=project_id,
                lock=lock,
            )
            if exact is None:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=node.binding.source,
                        selected_release=None,
                        result_source=node.binding.source,
                        result_release=None,
                        blocking_reason=f"Selected Agent {node.binding.source.title()} snapshot is unavailable.",
                        result_resolution="blocked",
                    )
                )
                continue
            plans.append(
                _NodePlan(
                    node=node,
                    selected_source=node.binding.source,
                    selected_release=exact,
                    result_source=node.binding.source,
                    result_release=exact,
                    result_resolution="retained",
                )
            )
        return plans

    async def _plan_release_nodes(
        self,
        session: AsyncSession,
        *,
        definition: NetworkDefinition,
        resolved_bindings: dict[str, Any],
        project_id: UUID,
        lock: bool,
    ) -> list[_NodePlan]:
        plans: list[_NodePlan] = []
        for node in definition.nodes:
            binding = resolved_bindings.get(str(node.id)) or {}
            release_id = binding.get("release_id")
            source = await self._release_by_id(
                session,
                release_id=release_id,
                project_id=project_id,
                agent_id=node.agent_id,
                lock=lock,
            )
            if source is None:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=str(binding.get("binding_source") or "staging"),
                        selected_release=None,
                        result_source="release",
                        result_release=None,
                        blocking_reason="Agent snapshot pinned by Network Staging is unavailable.",
                        result_resolution="blocked",
                    )
                )
                continue
            snapshot_kind = getattr(source, "snapshot_kind", None)
            if snapshot_kind == "release":
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="release",
                        selected_release=source,
                        result_source="release",
                        result_release=source,
                        result_resolution="retained",
                    )
                )
                continue
            if snapshot_kind != "staging":
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source=str(snapshot_kind or "unknown"),
                        selected_release=source,
                        result_source="release",
                        result_release=None,
                        blocking_reason="Network Staging contains an invalid Agent snapshot kind.",
                        result_resolution="blocked",
                    )
                )
                continue
            equivalent = await self._equivalent_release(
                session,
                source=source,
                lock=lock,
            )
            if equivalent is not None:
                plans.append(
                    _NodePlan(
                        node=node,
                        selected_source="staging",
                        selected_release=source,
                        result_source="release",
                        result_release=equivalent,
                        reuse_reason="An immutable Agent Release already matches this Staging snapshot.",
                        result_resolution="equivalent_reused",
                    )
                )
                continue
            plans.append(
                _NodePlan(
                    node=node,
                    selected_source="staging",
                    selected_release=source,
                    result_source="release",
                    result_release=None,
                    action_required="publish_staging_to_release",
                    action_id=self._action_id("release", source),
                    result_resolution="promoted",
                )
            )
        return plans

    async def _exact_binding_release(
        self,
        session: AsyncSession,
        *,
        node: NetworkNode,
        project_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        release = await self._release_by_id(
            session,
            release_id=node.binding.release_id,
            project_id=project_id,
            agent_id=node.agent_id,
            lock=lock,
        )
        if release is None:
            return None
        return release if getattr(release, "snapshot_kind", None) == node.binding.source else None

    async def _latest_by_status(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        agent_id: UUID,
        status: str,
        lock: bool,
    ) -> AgentRelease | None:
        statement = (
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.project_id == project_id,
                AgentReleaseModel.agent_id == agent_id,
                AgentReleaseModel.status == status,
            )
            .order_by(
                AgentReleaseModel.updated_at.desc(),
                AgentReleaseModel.created_at.desc(),
            )
            .limit(1)
        )
        if lock:
            statement = statement.with_for_update()
        model = await session.scalar(statement)
        return agent_release_model_to_entity(model) if model is not None else None

    async def _release_by_id(
        self,
        session: AsyncSession,
        *,
        release_id: UUID | str | None,
        project_id: UUID,
        agent_id: UUID,
        lock: bool,
    ) -> AgentRelease | None:
        if release_id is None:
            return None
        try:
            parsed_id = release_id if isinstance(release_id, UUID) else UUID(str(release_id))
        except (TypeError, ValueError):
            return None
        model = await session.get(AgentReleaseModel, parsed_id, with_for_update=lock)
        if (
            model is None
            or model.project_id != project_id
            or model.agent_id != agent_id
        ):
            return None
        return agent_release_model_to_entity(model)

    async def _equivalent_release(
        self,
        session: AsyncSession,
        *,
        source: AgentRelease,
        lock: bool,
    ) -> AgentRelease | None:
        statement = (
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.project_id == source.project_id,
                AgentReleaseModel.agent_id == source.agent_id,
                AgentReleaseModel.snapshot_kind == "release",
            )
            .order_by(AgentReleaseModel.created_at.desc())
        )
        if lock:
            statement = statement.with_for_update()
        result = await session.execute(statement)
        for model in result.scalars():
            candidate = agent_release_model_to_entity(model)
            if release_snapshots_equal(candidate, source):
                return candidate
        return None

    @staticmethod
    def _action_id(prefix: str, release: AgentRelease) -> str:
        return (
            f"{prefix}:{release.agent_id}:{release.id}:"
            f"{release_snapshot_hash(release)[:16]}"
        )

    def _preview_payload(
        self,
        *,
        network: NetworkModel,
        environment: NetworkEnvironment,
        source_version: NetworkVersionModel | None,
        definition: NetworkDefinition,
        plans: list[_NodePlan],
    ) -> dict[str, Any]:
        actions: list[dict[str, Any]] = []
        seen_actions: set[str] = set()
        nodes: list[dict[str, Any]] = []
        bindings: dict[str, dict[str, Any]] = {}
        missing_agent_ids: list[str] = []

        for plan in plans:
            selected = plan.selected_release
            result = plan.result_release
            if plan.blocking_reason:
                missing_agent_ids.append(str(plan.node.agent_id))
            if plan.action_id and plan.action_id not in seen_actions:
                seen_actions.add(plan.action_id)
                actions.append(
                    {
                        "id": plan.action_id,
                        "agent_id": str(plan.node.agent_id),
                        "agent_name": (selected.name if selected else None) or plan.node.label,
                        "action": plan.action_required,
                        "source_release_id": str(selected.id) if selected else "",
                        "source_version": selected.version if selected else "draft",
                        "source_snapshot_hash": plan.snapshot_hash,
                    }
                )
            nodes.append(
                {
                    "node_id": str(plan.node.id),
                    "agent_id": str(plan.node.agent_id),
                    "agent_name": (selected.name if selected else None) or plan.node.label,
                    "selected_source": plan.selected_source,
                    "selected_ref": str(selected.id) if selected else None,
                    "selected_version": selected.version if selected else None,
                    "result_source": plan.result_source,
                    "result_ref": str(result.id) if result else None,
                    "result_version": result.version if result else None,
                    "result_will_be_created": bool(plan.action_required),
                    "result_resolution": plan.result_resolution,
                    "action_required": plan.action_required,
                    "action_id": plan.action_id,
                    "blocking_reason": plan.blocking_reason,
                    "reuse_reason": plan.reuse_reason,
                    "snapshot_hash": plan.snapshot_hash,
                }
            )
            bindings[str(plan.node.id)] = {
                "node_id": str(plan.node.id),
                "agent_id": str(plan.node.agent_id),
                "binding_source": plan.result_source,
                "release_id": str(result.id) if result else None,
                "release_version": result.version if result else None,
                "snapshot_hash": release_snapshot_hash(result) if result else plan.snapshot_hash,
            }

        unique_missing = list(dict.fromkeys(missing_agent_ids))
        equivalent_reused = sum(
            1 for plan in plans if plan.result_resolution == "equivalent_reused"
        )
        draft_promotions = sum(
            1 for action in actions if action["action"] == "promote_draft_to_staging"
        )
        release_promotions = sum(
            1 for action in actions if action["action"] == "publish_staging_to_release"
        )
        staging_retained = sum(
            1
            for plan in plans
            if plan.result_source == "staging" and plan.action_required is None
        )
        releases_retained = sum(
            1
            for plan in plans
            if plan.result_source == "release" and plan.action_required is None
        )
        return {
            "environment": environment.value,
            "network_revision": network.draft_revision,
            "network_version_id": str(source_version.id) if source_version else None,
            "ready": not unique_missing,
            "nodes": nodes,
            "actions": actions,
            "bindings": bindings,
            "missing_agent_ids": unique_missing,
            "reused_agent_count": equivalent_reused + staging_retained + releases_retained,
            "draft_promotions": draft_promotions,
            "staging_retained": staging_retained,
            "release_promotions": release_promotions,
            "releases_retained": releases_retained,
            "equivalent_snapshots_reused": equivalent_reused,
            "definition": definition.to_dict(),
        }
