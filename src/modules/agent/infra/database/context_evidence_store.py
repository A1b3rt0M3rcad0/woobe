from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select

from modules.agent.infra.database.context_models import (
    ContextContributionModel,
    ContextSnapshotModel,
    ModelInvocationModel,
)
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork


def _uuid(value: Any) -> UUID | None:
    if value in {None, ""}:
        return None
    try:
        return value if isinstance(value, UUID) else UUID(str(value))
    except (TypeError, ValueError):
        return None


def _datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _as_int(value: Any) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _as_float(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return None


class ContextEvidenceStore:
    """Persist Context evidence inside the Agent UnitOfWork terminal transaction."""

    def __init__(self, uow: AgentUnitOfWork) -> None:
        self._uow = uow

    async def persist_from_calls(
        self,
        *,
        agent_run_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        trace_id: UUID | None,
        network_execution_id: UUID | None,
        network_invocation_id: UUID | None,
        calls: list[dict[str, Any]],
    ) -> None:
        session = self._uow.session
        for call in calls:
            if not isinstance(call, dict):
                continue
            snapshot = call.get("context_snapshot")
            if not isinstance(snapshot, dict):
                continue
            invocation_id = _uuid(call.get("call_id"))
            snapshot_id = _uuid(snapshot.get("id"))
            if invocation_id is None or snapshot_id is None:
                continue
            if await session.get(ModelInvocationModel, invocation_id) is not None:
                continue

            session.add(
                ModelInvocationModel(
                    id=invocation_id,
                    project_id=project_id,
                    agent_run_id=agent_run_id,
                    agent_id=agent_id,
                    trace_id=trace_id,
                    network_execution_id=network_execution_id,
                    network_invocation_id=network_invocation_id,
                    call_index=int(call.get("call_index") or 0),
                    phase=str(call.get("phase") or "model_invocation"),
                    provider=str(call.get("provider") or ""),
                    model=str(call.get("model") or ""),
                    provider_model_id=_uuid(call.get("provider_model_id")),
                    provider_credential_id=_uuid(call.get("provider_credential_id")),
                    status=str(call.get("status") or "unknown"),
                    started_at=_datetime(call.get("started_at")),
                    ended_at=_datetime(call.get("ended_at")),
                    latency_ms=_as_int(call.get("latency_ms")),
                    input_units=_as_int(call.get("input_tokens")),
                    output_units=_as_int(call.get("output_tokens")),
                    total_units=_as_int(call.get("total_tokens")),
                    cost_usd=_as_float(call.get("cost_usd")),
                    usage_complete=(
                        call.get("usage_complete")
                        if isinstance(call.get("usage_complete"), bool)
                        else None
                    ),
                    error=str(call.get("error")) if call.get("error") else None,
                    data={
                        key: call.get(key)
                        for key in (
                            "cost_status",
                            "cost_reason",
                            "pricing_id",
                            "upstream_status",
                            "upstream_error_code",
                        )
                        if call.get(key) is not None
                    },
                )
            )
            session.add(
                ContextSnapshotModel(
                    id=snapshot_id,
                    project_id=project_id,
                    model_invocation_id=invocation_id,
                    agent_run_id=agent_run_id,
                    policy_schema_version=int(
                        snapshot.get("policy_schema_version") or 1
                    ),
                    policy_hash=str(snapshot.get("policy_hash") or ""),
                    model_capacity_units=_as_int(
                        snapshot.get("model_capacity_units")
                    ),
                    reserved_output_units=_as_int(
                        snapshot.get("reserved_output_units")
                    ),
                    runtime_reserve_units=int(
                        snapshot.get("runtime_reserve_units") or 0
                    ),
                    usable_input_budget=_as_int(
                        snapshot.get("usable_input_budget")
                    ),
                    estimated_input_units=int(
                        snapshot.get("estimated_input_units") or 0
                    ),
                    reported_input_units=_as_int(
                        snapshot.get("reported_input_units")
                    ),
                    utilization=_as_float(snapshot.get("utilization")),
                    pressure_status=str(
                        snapshot.get("pressure_status") or "UNKNOWN"
                    ),
                    measurement_status=str(
                        snapshot.get("measurement_status") or "unknown"
                    ),
                    manifest=(
                        dict(snapshot.get("manifest"))
                        if isinstance(snapshot.get("manifest"), dict)
                        else {}
                    ),
                    materialized_hash=str(
                        snapshot.get("materialized_hash") or ""
                    ),
                    retention_mode=str(
                        snapshot.get("retention_mode") or "references_only"
                    ),
                    reproduction_level=str(
                        snapshot.get("reproduction_level") or "manifest_only"
                    ),
                )
            )

            raw_contributions = snapshot.get("contributions")
            if not isinstance(raw_contributions, list):
                continue
            for ordinal, item in enumerate(raw_contributions):
                if not isinstance(item, dict):
                    continue
                contribution_id = _uuid(item.get("id"))
                if contribution_id is None:
                    continue
                session.add(
                    ContextContributionModel(
                        id=contribution_id,
                        snapshot_id=snapshot_id,
                        ordinal=int(
                            item.get("ordinal")
                            if isinstance(item.get("ordinal"), int)
                            else ordinal
                        ),
                        source_type=str(item.get("source_type") or "RUNTIME"),
                        source_ref=(
                            str(item.get("source_ref"))
                            if item.get("source_ref") is not None
                            else None
                        ),
                        parent_ref=(
                            str(item.get("parent_ref"))
                            if item.get("parent_ref") is not None
                            else None
                        ),
                        modality=str(item.get("modality") or "text"),
                        priority=str(item.get("priority") or "DYNAMIC"),
                        raw_units=_as_int(item.get("raw_units")),
                        materialized_units=_as_int(
                            item.get("materialized_units")
                        ),
                        selection_method=(
                            str(item.get("selection_method"))
                            if item.get("selection_method")
                            else None
                        ),
                        relevance_score=_as_float(
                            item.get("relevance_score")
                        ),
                        transformations=(
                            list(item.get("transformations"))
                            if isinstance(item.get("transformations"), list)
                            else []
                        ),
                        trust=(
                            str(item.get("trust"))
                            if item.get("trust")
                            else None
                        ),
                        sensitivity=(
                            str(item.get("sensitivity"))
                            if item.get("sensitivity")
                            else None
                        ),
                        integrity_hash=(
                            str(item.get("integrity_hash"))
                            if item.get("integrity_hash")
                            else None
                        ),
                        data=(
                            dict(item.get("metadata"))
                            if isinstance(item.get("metadata"), dict)
                            else {}
                        ),
                    )
                )
        await session.flush()

    async def list_by_run(self, agent_run_id: UUID) -> list[dict[str, Any]]:
        session = self._uow.session
        invocations = list(
            (
                await session.execute(
                    select(ModelInvocationModel)
                    .where(ModelInvocationModel.agent_run_id == agent_run_id)
                    .order_by(
                        ModelInvocationModel.call_index.asc(),
                        ModelInvocationModel.created_at.asc(),
                    )
                )
            ).scalars().all()
        )
        result: list[dict[str, Any]] = []
        for invocation in invocations:
            snapshot = await session.scalar(
                select(ContextSnapshotModel).where(
                    ContextSnapshotModel.model_invocation_id == invocation.id
                )
            )
            if snapshot is None:
                continue
            contributions = list(
                (
                    await session.execute(
                        select(ContextContributionModel)
                        .where(ContextContributionModel.snapshot_id == snapshot.id)
                        .order_by(ContextContributionModel.ordinal.asc())
                    )
                ).scalars().all()
            )
            result.append(
                {
                    "id": str(invocation.id),
                    "call_index": invocation.call_index,
                    "phase": invocation.phase,
                    "provider": invocation.provider,
                    "model": invocation.model,
                    "status": invocation.status,
                    "latency_ms": invocation.latency_ms,
                    "input_units": invocation.input_units,
                    "output_units": invocation.output_units,
                    "total_units": invocation.total_units,
                    "cost_usd": (
                        float(invocation.cost_usd)
                        if invocation.cost_usd is not None
                        else None
                    ),
                    "started_at": invocation.started_at,
                    "ended_at": invocation.ended_at,
                    "context_snapshot": {
                        "id": str(snapshot.id),
                        "policy_schema_version": snapshot.policy_schema_version,
                        "policy_hash": snapshot.policy_hash,
                        "model_capacity_units": snapshot.model_capacity_units,
                        "reserved_output_units": snapshot.reserved_output_units,
                        "runtime_reserve_units": snapshot.runtime_reserve_units,
                        "usable_input_budget": snapshot.usable_input_budget,
                        "estimated_input_units": snapshot.estimated_input_units,
                        "reported_input_units": snapshot.reported_input_units,
                        "utilization": snapshot.utilization,
                        "pressure_status": snapshot.pressure_status,
                        "measurement_status": snapshot.measurement_status,
                        "manifest": dict(snapshot.manifest or {}),
                        "materialized_hash": snapshot.materialized_hash,
                        "retention_mode": snapshot.retention_mode,
                        "reproduction_level": snapshot.reproduction_level,
                        "contributions": [
                            {
                                "id": str(item.id),
                                "ordinal": item.ordinal,
                                "source_type": item.source_type,
                                "source_ref": item.source_ref,
                                "parent_ref": item.parent_ref,
                                "modality": item.modality,
                                "priority": item.priority,
                                "raw_units": item.raw_units,
                                "materialized_units": item.materialized_units,
                                "selection_method": item.selection_method,
                                "relevance_score": item.relevance_score,
                                "transformations": list(
                                    item.transformations or []
                                ),
                                "trust": item.trust,
                                "sensitivity": item.sensitivity,
                                "integrity_hash": item.integrity_hash,
                                "metadata": dict(item.data or {}),
                            }
                            for item in contributions
                        ],
                    },
                }
            )
        return result
