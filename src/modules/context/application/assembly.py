from __future__ import annotations

import hashlib
import json
import math
from copy import deepcopy
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

import uuid6

from modules.context.application.policy import ContextPolicyV1, context_policy_hash
from modules.context.domain.entities import (
    ContextContribution,
    ContextMeasurementStatus,
    ContextPressureStatus,
    ContextPriority,
    ContextReproductionLevel,
    ContextSnapshot,
    ContextSourceType,
)


class ContextBudgetExceeded(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    messages: list[Any]
    snapshot: ContextSnapshot


def _json(value: Any) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def estimate_input_units(value: Any) -> int:
    """Conservative text estimator. It is intentionally marked as estimated."""
    text = value if isinstance(value, str) else _json(value)
    if not text:
        return 0
    return max(1, math.ceil(len(text) / 4))


def _message_text(message: Any) -> str:
    content = getattr(message, "content", "")
    if isinstance(content, str):
        text = content
    else:
        text = _json(content)
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        text += "\n" + _json(tool_calls)
    return text


def _context_metadata(message: Any) -> dict[str, Any]:
    additional = getattr(message, "additional_kwargs", None)
    if not isinstance(additional, dict):
        return {}
    raw = additional.get("woobe_context")
    return dict(raw) if isinstance(raw, dict) else {}


def _classify_message(
    message: Any,
    *,
    index: int,
    latest_user_index: int | None,
    delegated: bool,
) -> ContextSourceType:
    explicit = _context_metadata(message).get("source_type")
    if explicit:
        try:
            return ContextSourceType(str(explicit).upper())
        except ValueError:
            pass

    name = type(message).__name__
    if name == "ToolMessage":
        return ContextSourceType.TOOL
    if name == "SystemMessage":
        return ContextSourceType.SYSTEM
    if name == "HumanMessage":
        if latest_user_index == index:
            return ContextSourceType.DELEGATION if delegated else ContextSourceType.USER_INPUT
        return ContextSourceType.SESSION
    if name == "AIMessage":
        if latest_user_index is not None and index > latest_user_index:
            return ContextSourceType.RUNTIME
        return ContextSourceType.SESSION
    return ContextSourceType.RUNTIME


def _priority(source: ContextSourceType) -> ContextPriority:
    if source in {ContextSourceType.SYSTEM, ContextSourceType.USER_INPUT}:
        return ContextPriority.MANDATORY
    if source == ContextSourceType.DELEGATION:
        return ContextPriority.HIGH
    if source == ContextSourceType.SESSION:
        return ContextPriority.HIGH
    if source in {ContextSourceType.KNOWLEDGE, ContextSourceType.TOOL, ContextSourceType.RUNTIME}:
        return ContextPriority.DYNAMIC
    return ContextPriority.OPTIONAL


def _copy_with_content(message: Any, content: str) -> Any:
    copier = getattr(message, "model_copy", None)
    if callable(copier):
        return copier(update={"content": content})
    clone = deepcopy(message)
    clone.content = content
    return clone


def _trim_message_to_units(message: Any, max_units: int) -> tuple[Any, bool]:
    text = _message_text(message)
    current = estimate_input_units(text)
    if current <= max_units:
        return message, False
    if max_units <= 0:
        return _copy_with_content(message, ""), True
    max_chars = max_units * 4
    content = getattr(message, "content", "")
    if not isinstance(content, str):
        content = _json(content)
    if len(content) <= max_chars:
        return message, False
    suffix = "\n[context truncated by Woobe budget]"
    keep = max(0, max_chars - len(suffix))
    return _copy_with_content(message, content[:keep] + suffix), True


def _effective_budget(policy: ContextPolicyV1, runtime_context: Any) -> tuple[int | None, int | None, int, int | None]:
    raw_capacity = getattr(runtime_context, "model_capacity_units", None) if runtime_context else None
    capacity = raw_capacity if isinstance(raw_capacity, int) and raw_capacity > 0 else None
    raw_reserved = getattr(runtime_context, "reserved_output_units", None) if runtime_context else None
    reserved = raw_reserved if isinstance(raw_reserved, int) and raw_reserved >= 0 else None
    runtime_reserve = policy.budget.runtime_reserve_units

    model_usable = None
    if capacity is not None:
        model_usable = max(0, capacity - (reserved or 0) - runtime_reserve)
    configured = policy.budget.max_input_units
    if model_usable is not None and configured is not None:
        usable = min(model_usable, configured)
    else:
        usable = model_usable if model_usable is not None else configured
    return capacity, reserved, runtime_reserve, usable


def _pressure(utilization: float | None, policy: ContextPolicyV1) -> ContextPressureStatus:
    if utilization is None:
        return ContextPressureStatus.UNKNOWN
    if utilization >= policy.pressure.critical_at:
        return ContextPressureStatus.CRITICAL
    if utilization >= policy.pressure.high_at:
        return ContextPressureStatus.HIGH
    if utilization >= policy.pressure.moderate_at:
        return ContextPressureStatus.MODERATE
    return ContextPressureStatus.LOW


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _source_runtime_metadata(source: ContextSourceType, runtime_context: Any) -> dict[str, Any]:
    if runtime_context is None:
        return {}
    if source == ContextSourceType.KNOWLEDGE:
        rag = getattr(runtime_context, "rag_metadata", None)
        sources = getattr(runtime_context, "context_rag_sources", None)
        return {
            "rag": dict(rag) if isinstance(rag, dict) else None,
            "sources": list(sources) if isinstance(sources, list) else [],
        }
    if source == ContextSourceType.SESSION:
        selection = getattr(runtime_context, "context_selection_metadata", None)
        return dict(selection) if isinstance(selection, dict) else {}
    if source == ContextSourceType.DELEGATION:
        return {
            "network_execution_id": str(getattr(runtime_context, "network_execution_id", "") or "") or None,
            "network_invocation_id": str(getattr(runtime_context, "network_invocation_id", "") or "") or None,
            "parent_invocation_id": str(getattr(runtime_context, "parent_invocation_id", "") or "") or None,
            "network_node_id": str(getattr(runtime_context, "network_node_id", "") or "") or None,
        }
    return {}


def _contribution(
    *,
    snapshot_id: UUID,
    ordinal: int,
    source: ContextSourceType,
    message: Any,
    units: int,
    transformations: tuple[str, ...],
    runtime_context: Any,
) -> ContextContribution:
    metadata = _context_metadata(message)
    source_ref = metadata.get("source_ref")
    parent_ref = metadata.get("parent_ref")
    merged_metadata = {**_source_runtime_metadata(source, runtime_context), **metadata}
    text = _message_text(message)
    return ContextContribution(
        snapshot_id=snapshot_id,
        ordinal=ordinal,
        source_type=source,
        source_ref=str(source_ref) if source_ref is not None else None,
        parent_ref=str(parent_ref) if parent_ref is not None else None,
        priority=_priority(source),
        raw_units=metadata.get("raw_units") if isinstance(metadata.get("raw_units"), int) else units,
        materialized_units=units,
        selection_method=str(metadata.get("selection_method") or "runtime_materialization"),
        relevance_score=(
            float(metadata["relevance_score"])
            if isinstance(metadata.get("relevance_score"), (int, float))
            else None
        ),
        transformations=transformations,
        trust=str(metadata.get("trust") or "internal"),
        sensitivity=str(metadata.get("sensitivity") or "internal"),
        integrity_hash=_hash_text(text),
        metadata=merged_metadata,
    )


def _session_keep_indices(messages: list[Any], sources: list[ContextSourceType], policy: ContextPolicyV1) -> set[int]:
    indices = [index for index, source in enumerate(sources) if source == ContextSourceType.SESSION]
    selected = indices[-policy.session.max_messages :]
    if policy.session.max_units is None:
        return set(selected)
    kept: list[int] = []
    used = 0
    for index in reversed(selected):
        units = estimate_input_units(_message_text(messages[index]))
        if kept and used + units > policy.session.max_units:
            continue
        if not kept and units > policy.session.max_units:
            trimmed, _ = _trim_message_to_units(messages[index], policy.session.max_units)
            messages[index] = trimmed
            units = estimate_input_units(_message_text(trimmed))
        kept.append(index)
        used += units
    return set(kept)


def assemble_context(
    *,
    messages: list[Any],
    model_invocation_id: UUID,
    agent_run_id: UUID,
    project_id: UUID,
    provider: str,
    model: str,
    runtime_context: Any,
    policy: ContextPolicyV1,
) -> ContextAssemblyResult:
    working = list(messages)
    delegated = bool(getattr(runtime_context, "parent_invocation_id", None)) if runtime_context else False
    latest_user_index = None
    for index in range(len(working) - 1, -1, -1):
        if type(working[index]).__name__ == "HumanMessage":
            latest_user_index = index
            break

    sources = [
        _classify_message(
            message,
            index=index,
            latest_user_index=latest_user_index,
            delegated=delegated,
        )
        for index, message in enumerate(working)
    ]

    allowed = set(policy.allowed_sources)
    current_source = ContextSourceType.DELEGATION if delegated else ContextSourceType.USER_INPUT
    if ContextSourceType.SYSTEM not in allowed or current_source not in allowed:
        raise ContextBudgetExceeded("Context Policy excludes mandatory context sources")

    session_keep = _session_keep_indices(working, sources, policy)
    keep = [True] * len(working)
    exclusions: dict[str, int] = {}
    transformations_by_index: dict[int, list[str]] = {}
    for index, source in enumerate(sources):
        if source not in allowed:
            keep[index] = False
            exclusions[source.value] = exclusions.get(source.value, 0) + 1
        elif source == ContextSourceType.SESSION and index not in session_keep:
            keep[index] = False
            exclusions[source.value] = exclusions.get(source.value, 0) + 1

    def apply_source_cap(source_type: ContextSourceType, cap: int | None) -> None:
        if cap is None:
            return
        remaining = cap
        for index in range(len(working) - 1, -1, -1):
            if not keep[index] or sources[index] != source_type:
                continue
            units = estimate_input_units(_message_text(working[index]))
            if units <= remaining:
                remaining -= units
                continue
            if remaining <= 0:
                keep[index] = False
                exclusions[source_type.value] = exclusions.get(source_type.value, 0) + 1
                continue
            trimmed, changed = _trim_message_to_units(working[index], remaining)
            working[index] = trimmed
            if changed:
                transformations_by_index.setdefault(index, []).append("source_budget_truncate")
            remaining = 0

    apply_source_cap(ContextSourceType.KNOWLEDGE, policy.knowledge.max_units)
    apply_source_cap(ContextSourceType.TOOL, policy.tools.max_result_units)
    apply_source_cap(ContextSourceType.DELEGATION, policy.delegation.max_units)

    capacity, reserved, runtime_reserve, usable = _effective_budget(policy, runtime_context)

    def total_units() -> int:
        tool_definitions = getattr(runtime_context, "active_tool_definitions", None) if runtime_context else None
        total = sum(
            estimate_input_units(_message_text(message))
            for index, message in enumerate(working)
            if keep[index]
        )
        if isinstance(tool_definitions, list) and tool_definitions:
            total += estimate_input_units(tool_definitions)
        return total

    if usable is not None:
        overflow = total_units() - usable
        if overflow > 0:
            for index, source in enumerate(sources):
                if overflow <= 0:
                    break
                if keep[index] and source == ContextSourceType.SESSION:
                    units = estimate_input_units(_message_text(working[index]))
                    keep[index] = False
                    exclusions[source.value] = exclusions.get(source.value, 0) + 1
                    overflow -= units
        if overflow > 0:
            for source_type in (ContextSourceType.KNOWLEDGE, ContextSourceType.TOOL, ContextSourceType.RUNTIME):
                for index in range(len(working) - 1, -1, -1):
                    if overflow <= 0:
                        break
                    if not keep[index] or sources[index] != source_type:
                        continue
                    current_units = estimate_input_units(_message_text(working[index]))
                    target_units = max(1, current_units - overflow)
                    trimmed, changed = _trim_message_to_units(working[index], target_units)
                    if changed:
                        working[index] = trimmed
                        transformations_by_index.setdefault(index, []).append("global_budget_truncate")
                    overflow = total_units() - usable
                if overflow <= 0:
                    break
        if total_units() > usable:
            raise ContextBudgetExceeded(
                f"Mandatory context exceeds usable input budget: {total_units()} > {usable}"
            )

    materialized_messages = [message for index, message in enumerate(working) if keep[index]]
    estimated = total_units()
    snapshot_id = uuid6.uuid7()
    contributions: list[ContextContribution] = []
    ordinal = 0
    for index, message in enumerate(working):
        if not keep[index]:
            continue
        source = sources[index]
        units = estimate_input_units(_message_text(message))
        contributions.append(
            _contribution(
                snapshot_id=snapshot_id,
                ordinal=ordinal,
                source=source,
                message=message,
                units=units,
                transformations=tuple(transformations_by_index.get(index, [])),
                runtime_context=runtime_context,
            )
        )
        ordinal += 1

    tool_definitions = getattr(runtime_context, "active_tool_definitions", None) if runtime_context else None
    if isinstance(tool_definitions, list) and tool_definitions:
        tool_units = estimate_input_units(tool_definitions)
        tool_text = _json(tool_definitions)
        contributions.append(
            ContextContribution(
                snapshot_id=snapshot_id,
                ordinal=ordinal,
                source_type=ContextSourceType.SYSTEM,
                source_ref="runtime_tool_definitions",
                priority=ContextPriority.MANDATORY,
                raw_units=tool_units,
                materialized_units=tool_units,
                selection_method="runtime_binding",
                trust="system-controlled",
                sensitivity="internal",
                integrity_hash=_hash_text(tool_text),
                metadata={"tool_definition_count": len(tool_definitions)},
            )
        )

    source_summary: dict[str, dict[str, int]] = {}
    for contribution in contributions:
        item = source_summary.setdefault(contribution.source_type.value, {"count": 0, "units": 0})
        item["count"] += 1
        item["units"] += int(contribution.materialized_units or 0)

    utilization = (estimated / usable) if usable and usable > 0 else None
    policy_hash = context_policy_hash(policy)
    materialized_payload = [
        {
            "type": type(message).__name__,
            "content": getattr(message, "content", None),
            "tool_calls": getattr(message, "tool_calls", None),
            "tool_call_id": getattr(message, "tool_call_id", None),
        }
        for message in materialized_messages
    ]
    if isinstance(tool_definitions, list) and tool_definitions:
        materialized_payload.append({"tool_definitions": tool_definitions})
    materialized_hash = _hash_text(_json(materialized_payload))

    selection = getattr(runtime_context, "context_selection_metadata", None) if runtime_context else None
    rag_metadata = getattr(runtime_context, "rag_metadata", None) if runtime_context else None
    manifest = {
        "schema_version": 1,
        "snapshot_id": str(snapshot_id),
        "model_invocation_id": str(model_invocation_id),
        "agent_run_id": str(agent_run_id),
        "provider": provider,
        "model": model,
        "policy_hash": policy_hash,
        "sources": source_summary,
        "estimated_input_units": estimated,
        "model_capacity_units": capacity,
        "reserved_output_units": reserved,
        "runtime_reserve_units": runtime_reserve,
        "usable_input_budget": usable,
        "utilization": utilization,
        "exclusions": exclusions,
        "session_selection": dict(selection) if isinstance(selection, dict) else None,
        "knowledge": dict(rag_metadata) if isinstance(rag_metadata, dict) else None,
    }
    snapshot = ContextSnapshot(
        id=snapshot_id,
        project_id=project_id,
        model_invocation_id=model_invocation_id,
        agent_run_id=agent_run_id,
        policy_schema_version=policy.schema_version,
        policy_hash=policy_hash,
        model_capacity_units=capacity,
        reserved_output_units=reserved,
        runtime_reserve_units=runtime_reserve,
        usable_input_budget=usable,
        estimated_input_units=estimated,
        utilization=utilization,
        pressure_status=_pressure(utilization, policy),
        measurement_status=ContextMeasurementStatus.ESTIMATED,
        manifest=manifest,
        materialized_hash=materialized_hash,
        retention_mode=policy.retention.materialized_content,
        reproduction_level=ContextReproductionLevel.MANIFEST_ONLY,
        contributions=tuple(contributions),
    )
    return ContextAssemblyResult(messages=materialized_messages, snapshot=snapshot)


def enrich_snapshot_with_reported_usage(snapshot: ContextSnapshot, reported_input_units: int | None) -> ContextSnapshot:
    if reported_input_units is None:
        return snapshot
    utilization = (
        reported_input_units / snapshot.usable_input_budget
        if snapshot.usable_input_budget and snapshot.usable_input_budget > 0
        else snapshot.utilization
    )
    manifest = dict(snapshot.manifest)
    manifest["reported_input_units"] = reported_input_units
    manifest["utilization"] = utilization
    return replace(
        snapshot,
        reported_input_units=reported_input_units,
        utilization=utilization,
        pressure_status=(
            ContextPressureStatus.UNKNOWN
            if utilization is None
            else snapshot.pressure_status
        ),
        measurement_status=ContextMeasurementStatus.REPORTED,
        manifest=manifest,
    )


def snapshot_to_dict(snapshot: ContextSnapshot) -> dict[str, Any]:
    return {
        "id": str(snapshot.id),
        "project_id": str(snapshot.project_id),
        "model_invocation_id": str(snapshot.model_invocation_id),
        "agent_run_id": str(snapshot.agent_run_id),
        "policy_schema_version": snapshot.policy_schema_version,
        "policy_hash": snapshot.policy_hash,
        "model_capacity_units": snapshot.model_capacity_units,
        "reserved_output_units": snapshot.reserved_output_units,
        "runtime_reserve_units": snapshot.runtime_reserve_units,
        "usable_input_budget": snapshot.usable_input_budget,
        "estimated_input_units": snapshot.estimated_input_units,
        "reported_input_units": snapshot.reported_input_units,
        "utilization": snapshot.utilization,
        "pressure_status": snapshot.pressure_status.value,
        "measurement_status": snapshot.measurement_status.value,
        "manifest": snapshot.manifest,
        "materialized_hash": snapshot.materialized_hash,
        "retention_mode": snapshot.retention_mode.value,
        "reproduction_level": snapshot.reproduction_level.value,
        "contributions": [
            {
                "id": str(item.id),
                "ordinal": item.ordinal,
                "source_type": item.source_type.value,
                "source_ref": item.source_ref,
                "parent_ref": item.parent_ref,
                "modality": item.modality,
                "priority": item.priority.value,
                "raw_units": item.raw_units,
                "materialized_units": item.materialized_units,
                "selection_method": item.selection_method,
                "relevance_score": item.relevance_score,
                "transformations": list(item.transformations),
                "trust": item.trust,
                "sensitivity": item.sensitivity,
                "integrity_hash": item.integrity_hash,
                "metadata": item.metadata,
            }
            for item in snapshot.contributions
        ],
    }
