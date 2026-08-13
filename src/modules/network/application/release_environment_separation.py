from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select

from modules.agent.domain.release_compatibility import classify_release_change
from modules.agent.domain.release_versioning import calculate_next_release_version
from modules.agent.infra.database.models import AgentReleaseModel


async def _copy_agent_snapshot_detached(
    self,
    session,
    source,
    *,
    target: str,
    promoted_by: UUID | None,
):
    if target == "staging":
        return await self._detached_release_base_copy_agent_snapshot(
            session,
            source,
            target=target,
            promoted_by=promoted_by,
        )
    if target != "release":
        raise ValueError(f"Unsupported Agent snapshot target: {target}")

    query = (
        select(AgentReleaseModel)
        .where(
            AgentReleaseModel.agent_id == source.agent_id,
            AgentReleaseModel.project_id == source.project_id,
            AgentReleaseModel.snapshot_kind == "release",
            AgentReleaseModel.id != source.id,
        )
        .order_by(AgentReleaseModel.created_at.desc())
        .with_for_update()
    )
    for candidate in (await session.scalars(query)).all():
        if self._same_agent_snapshot(candidate, source):
            return candidate

    releases = list(
        (
            await session.scalars(
                select(AgentReleaseModel).where(
                    AgentReleaseModel.agent_id == source.agent_id
                )
            )
        ).all()
    )
    active_production = next(
        (
            item
            for item in releases
            if item.status == "production" and item.snapshot_kind == "release"
        ),
        None,
    )
    historical = [
        item.version for item in releases if item.snapshot_kind == "release"
    ]
    change_kind = classify_release_change(active_production, source)
    version = calculate_next_release_version(historical, change_kind)
    excluded = {
        "id",
        "created_at",
        "updated_at",
        "version",
        "status",
        "snapshot_kind",
        "promoted_by",
        "promoted_at",
        "release_notes",
    }
    values = {
        column.name: deepcopy(getattr(source, column.name))
        for column in AgentReleaseModel.__table__.columns
        if column.name not in excluded
    }
    clone = AgentReleaseModel(
        **values,
        version=version,
        status="released",
        snapshot_kind="release",
        release_notes=source.release_notes,
        promoted_by=promoted_by,
        promoted_at=datetime.now(timezone.utc),
    )
    session.add(clone)
    await session.flush()
    return clone


async def _promotion_plan_with_explicit_results(
    self,
    session,
    definition,
    project_id,
    environment,
    *,
    lock: bool = False,
):
    plan = await self._detached_release_base_plan(
        session,
        definition,
        project_id,
        environment,
        lock=lock,
    )
    definition_nodes = {str(node.id): node for node in definition.nodes}
    counts = {
        "draft_promotions": 0,
        "staging_retained": 0,
        "release_promotions": 0,
        "releases_retained": 0,
        "equivalent_snapshots_reused": 0,
    }

    for item in plan.get("nodes", []):
        node = definition_nodes.get(str(item.get("node_id")))
        result_ref = item.get("selected_ref")
        result_version = item.get("selected_version")
        action = item.get("action_required")
        reuse_reason = item.get("reuse_reason")
        blocked = bool(item.get("blocking_reason"))

        original = None
        if node is not None and node.binding.source == "draft":
            query = select(AgentReleaseModel).where(
                AgentReleaseModel.project_id == project_id,
                AgentReleaseModel.agent_id == node.agent_id,
                AgentReleaseModel.status == "draft",
                AgentReleaseModel.snapshot_kind == "draft",
            )
            if lock:
                query = query.with_for_update()
            original = await session.scalar(query)
        elif node is not None and node.binding.release_id is not None:
            original = await session.get(AgentReleaseModel, node.binding.release_id)

        if original is not None:
            item["selected_ref"] = str(original.id)
            item["selected_version"] = original.version

        if blocked:
            resolution = "blocked"
        elif action:
            resolution = "promoted"
            result_ref = None
            result_version = None
            if action == "promote_draft_to_staging":
                counts["draft_promotions"] += 1
            else:
                counts["release_promotions"] += 1
        elif reuse_reason:
            resolution = "equivalent_reused"
            counts["equivalent_snapshots_reused"] += 1
        else:
            resolution = "retained"
            if item.get("result_source") == "staging":
                counts["staging_retained"] += 1
            elif item.get("result_source") == "release":
                counts["releases_retained"] += 1

        item["result_ref"] = result_ref
        item["result_version"] = result_version
        item["result_resolution"] = resolution
        item["result_will_be_created"] = bool(action)

    plan.update(counts)
    if plan.get("staging_preview") is not None:
        plan["staging_preview"].update(counts)
    if plan.get("release_preview") is not None:
        plan["release_preview"].update(counts)
        plan["release_preview"]["agent_productions_changed"] = 0
    return plan


def install_detached_network_agent_releases() -> None:
    from modules.network.application.service import NetworkApplicationService

    if hasattr(NetworkApplicationService, "_detached_release_base_plan"):
        return
    NetworkApplicationService._detached_release_base_plan = NetworkApplicationService._build_promotion_plan  # type: ignore[attr-defined]
    NetworkApplicationService._detached_release_base_copy_agent_snapshot = NetworkApplicationService._copy_agent_snapshot  # type: ignore[attr-defined]
    NetworkApplicationService._build_promotion_plan = _promotion_plan_with_explicit_results  # type: ignore[assignment]
    NetworkApplicationService._copy_agent_snapshot = _copy_agent_snapshot_detached  # type: ignore[assignment]
