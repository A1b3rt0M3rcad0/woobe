from __future__ import annotations

import hashlib
import json
from typing import Any

from modules.agent.application.context_assembly import (
    assemble_context,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_assembler import (
    ContextAssemblyOutput,
    ContextAssemblyRequest,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagedContribution,
    ContextManagerCapabilities,
    ContextSummaryRequest,
)


_SESSION_COMPACTION_KEY = "context.session.compaction"


def _serialized_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _message_signature(message: Any) -> str:
    payload = {
        "type": type(message).__name__,
        "content": getattr(message, "content", None),
        "tool_calls": getattr(message, "tool_calls", None),
        "tool_call_id": getattr(message, "tool_call_id", None),
    }
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _message_line(message: Any) -> str:
    role = type(message).__name__
    content = _serialized_content(getattr(message, "content", ""))
    tool_calls = getattr(message, "tool_calls", None) or ()
    tool_call_id = getattr(message, "tool_call_id", None)
    suffix = ""
    if tool_calls:
        suffix += f" tool_calls={_serialized_content(tool_calls)}"
    if tool_call_id:
        suffix += f" tool_call_id={tool_call_id}"
    return f"[{role}]{suffix}\n{content}"


def _effective_usable_units(
    request: ContextInspectionRequest,
) -> int | None:
    capacity = getattr(request.runtime_context, "model_capacity_units", None)
    capacity = capacity if isinstance(capacity, int) and capacity > 0 else None
    reserved = getattr(request.runtime_context, "reserved_output_units", None)
    reserved = reserved if isinstance(reserved, int) and reserved >= 0 else 0
    runtime_reserve = int(request.policy.budget.runtime_reserve_units or 0)
    model_usable = (
        max(0, capacity - reserved - runtime_reserve)
        if capacity is not None
        else None
    )
    configured = request.policy.budget.max_input_units
    if model_usable is not None and configured is not None:
        return min(model_usable, configured)
    return model_usable if model_usable is not None else configured


class StandardContextAssembler:
    """Programmable Standard Context Manager used by Woobe.

    The historical class name is preserved for compatibility. The implementation
    owns Context inspection, compaction and assembly decisions behind the stable
    Context Manager interface.
    """

    __slots__ = (
        "_compaction_keep_recent_messages",
        "_compaction_target_units",
    )

    def __init__(
        self,
        *,
        compaction_keep_recent_messages: int = 8,
        compaction_target_units: int = 2000,
    ) -> None:
        if compaction_keep_recent_messages < 1:
            raise ValueError("compaction_keep_recent_messages must be positive")
        if compaction_target_units < 1:
            raise ValueError("compaction_target_units must be positive")
        self._compaction_keep_recent_messages = compaction_keep_recent_messages
        self._compaction_target_units = compaction_target_units

    def inspect(
        self,
        request: ContextInspectionRequest,
    ) -> ContextInspectionOutput:
        replaced_indexes = {
            index
            for contribution in request.contributions
            for index in contribution.replaces_message_indexes
            if 0 <= index < len(request.messages)
        }
        estimated = sum(
            estimate_input_units(
                _serialized_content(getattr(message, "content", ""))
            )
            for index, message in enumerate(request.messages)
            if index not in replaced_indexes
        )
        estimated += sum(
            estimate_input_units(_serialized_content(item.content))
            for item in request.contributions
        )
        usable = _effective_usable_units(request)
        utilization = (
            estimated / usable
            if isinstance(usable, int) and usable > 0
            else None
        )
        if utilization is None:
            pressure = "UNKNOWN"
        elif utilization >= request.policy.pressure.critical_at:
            pressure = "CRITICAL"
        elif utilization >= request.policy.pressure.high_at:
            pressure = "HIGH"
        elif utilization >= request.policy.pressure.moderate_at:
            pressure = "MODERATE"
        else:
            pressure = "LOW"

        return ContextInspectionOutput(
            message_count=len(request.messages) - len(replaced_indexes),
            contribution_count=len(request.contributions),
            estimated_input_units=estimated,
            usable_input_units=usable,
            utilization=utilization,
            pressure=pressure,
        )

    async def compact(
        self,
        request: ContextCompactionRequest,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        inspection = self.inspect(
            ContextInspectionRequest(
                messages=request.messages,
                contributions=request.contributions,
                runtime_context=request.runtime_context,
                policy=request.policy,
            )
        )
        if inspection.pressure not in {"HIGH", "CRITICAL"}:
            return ContextCompactionOutput(
                changed=False,
                metadata={
                    "reason": "pressure_below_threshold",
                    "pressure": inspection.pressure,
                },
            )

        existing = next(
            (
                contribution
                for contribution in request.contributions
                if contribution.key == _SESSION_COMPACTION_KEY
            ),
            None,
        )
        already_replaced = set(
            existing.replaces_message_indexes if existing is not None else ()
        )

        latest_user_index: int | None = None
        for index in range(len(request.messages) - 1, -1, -1):
            if type(request.messages[index]).__name__ == "HumanMessage":
                latest_user_index = index
                break

        if latest_user_index is None:
            return ContextCompactionOutput(
                changed=False,
                metadata={"reason": "no_current_user_message"},
            )

        session_indexes = [
            index
            for index, message in enumerate(request.messages[:latest_user_index])
            if (
                type(message).__name__ in {"HumanMessage", "AIMessage", "ToolMessage"}
                and index not in already_replaced
            )
        ]
        if len(session_indexes) <= self._compaction_keep_recent_messages:
            return ContextCompactionOutput(
                changed=False,
                metadata={
                    "reason": "session_window_already_compact",
                    "pressure": inspection.pressure,
                },
            )

        compact_indexes = session_indexes[
            : -self._compaction_keep_recent_messages
        ]
        if not compact_indexes:
            return ContextCompactionOutput(changed=False)

        source_lines: list[str] = []
        if existing is not None and isinstance(existing.content, str):
            source_lines.append(
                "[PreviousSessionSummary]\n" + existing.content.strip()
            )
        source_lines.extend(
            _message_line(request.messages[index])
            for index in compact_indexes
        )

        usable = inspection.usable_input_units
        adaptive_target = self._compaction_target_units
        if isinstance(usable, int) and usable > 0:
            adaptive_target = min(
                adaptive_target,
                max(256, int(usable * 0.35)),
            )

        summary = await capabilities.summarize(
            ContextSummaryRequest(
                instruction=(
                    "Compact the supplied Session context for later Agent reasoning. "
                    "Preserve concrete facts, user intent, decisions, constraints, "
                    "unresolved work, important Tool results and identifiers. "
                    "Remove repetition and conversational filler. Do not invent "
                    "information. The result replaces the covered Session messages, "
                    f"so aim for at most approximately {adaptive_target} input units."
                ),
                input_text="\n\n".join(source_lines),
                target_units=adaptive_target,
                phase=request.phase,
            )
        )
        content = summary.content.strip()
        if not content:
            return ContextCompactionOutput(
                changed=False,
                metadata={"reason": "empty_summary"},
            )

        replaced = tuple(
            sorted(already_replaced.union(compact_indexes))
        )
        contribution = ContextManagedContribution(
            key=_SESSION_COMPACTION_KEY,
            source_type="SESSION",
            content=content,
            metadata={
                **dict(summary.metadata),
                "selection_method": "context_manager_compaction",
                "operation": "summarize_replace",
                "pressure": inspection.pressure,
                "target_units": adaptive_target,
                "covered_message_count": len(replaced),
                "covered_message_signatures": [
                    _message_signature(request.messages[index])
                    for index in replaced
                    if 0 <= index < len(request.messages)
                ],
            },
            replaces_message_indexes=replaced,
        )
        return ContextCompactionOutput(
            changed=True,
            upserts=(contribution,),
            metadata={
                "operation": "summarize_replace",
                "pressure": inspection.pressure,
                "replaced_message_count": len(replaced),
            },
        )

    def assemble(self, request: ContextAssemblyRequest) -> ContextAssemblyOutput:
        return assemble_context(
            messages=request.messages,
            model_invocation_id=request.model_invocation_id,
            agent_run_id=request.agent_run_id,
            project_id=request.project_id,
            provider=request.provider,
            model=request.model,
            runtime_context=request.runtime_context,
            policy=request.policy,
        )


__all__ = ["StandardContextAssembler"]
