from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import AgentToolModel
from modules.evaluation.application.context_pack import (
    _live_tool_payload,
    _snapshot_refs,
    _snapshot_tool_payload,
)
from modules.evaluation.application.target_resolver import ResolvedEvaluationTarget
from shared.infra.errors import ValidationError


async def build_target_tool_catalog(
    session: AsyncSession,
    *,
    target: ResolvedEvaluationTarget,
    project_id: UUID,
) -> dict[str, Any]:
    tool_ids, snapshots, _ = _snapshot_refs(target)
    snapshot_payload = {
        tool_id: _snapshot_tool_payload(tool_id, snapshot)
        for tool_id, snapshot in snapshots.items()
    }
    missing_snapshot_ids = sorted(
        (tool_id for tool_id in tool_ids if tool_id not in snapshot_payload),
        key=str,
    )

    if target.source_type == "release" and missing_snapshot_ids:
        raise ValidationError(
            "The selected Release does not contain immutable snapshots for all "
            "configured Tools. Publish a new Release before generating a "
            "target-bound Evaluator Suite."
        )

    live_payload: dict[UUID, dict[str, Any]] = {}
    if missing_snapshot_ids:
        live_tools = list(
            (
                await session.scalars(
                    select(AgentToolModel).where(
                        AgentToolModel.id.in_(missing_snapshot_ids),
                        AgentToolModel.project_id == project_id,
                        AgentToolModel.status == "active",
                    )
                )
            ).all()
        )
        live_payload = {item.id: _live_tool_payload(item) for item in live_tools}
        unresolved = [
            str(tool_id)
            for tool_id in missing_snapshot_ids
            if tool_id not in live_payload
        ]
        if unresolved:
            raise ValidationError(
                "The selected target references Tools that are unavailable in this "
                "Project: " + ", ".join(unresolved)
            )

    merged = {**snapshot_payload, **live_payload}
    tools = sorted(merged.values(), key=lambda item: str(item.get("name") or ""))
    if not tool_ids:
        status = "empty"
        source = "no_tools"
    elif not missing_snapshot_ids:
        status = "complete"
        source = "immutable_snapshot"
    else:
        status = "complete_with_live_fallback"
        source = "current_registry_fallback"

    return {
        "status": status,
        "source": source,
        "target_source_type": target.source_type,
        "target_snapshot_hash": target.snapshot_hash,
        "allowed_names": [str(item.get("name")) for item in tools if item.get("name")],
        "tools": tools,
        "missing_snapshot_tool_ids": [str(item) for item in missing_snapshot_ids],
        "immutable": target.source_type == "release" and not missing_snapshot_ids,
    }


__all__ = ["build_target_tool_catalog"]
