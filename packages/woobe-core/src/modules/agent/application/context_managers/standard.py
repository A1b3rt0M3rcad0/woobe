from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from langchain_core.messages import SystemMessage

from modules.agent.application.context_assembly import (
    assemble_context,
    estimate_input_units,
)
from modules.agent.application.interfaces.context_manager import (
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

_BOUND_CAPABILITIES_INSTRUCTION = (
    "The capabilities bound to this Model Invocation are the complete and authoritative "
    "set currently available to this Agent. Do not search for, list, discover, or invent "
    "additional capabilities. Do not infer capability availability from previous Session "
    "messages or prior executions. Use only the capabilities currently bound by the runtime "
    "when they are needed; otherwise answer directly."
)

_TOOL_GROUNDING_RUNTIME_RULES = (
    "Tool grounding rules:\n"
    "- The Tool definitions attached to this Model Invocation are the complete "
    "set of runtime Tools available to this Agent. Do not call another Tool just "
    "to discover which Tools exist.\n"
    "- Never invent identifiers, owners, repository names, URLs, resource IDs, "
    "tenant IDs, slugs or keys required by a Tool.\n"
    "- If a qualified identifier is missing, use a real discovery or search Tool "
    "when one is explicitly present in the attached Tool definitions.\n"
    "- If no discovery Tool is available, ask the user for the missing identifier.\n"
    "- Do not try guessed candidates or fabricated alternatives after a Tool rejects "
    "an identifier or reports that a resource was not found."
)

_SKILL_USAGE_INSTRUCTION = (
    "The installed Skill catalog contains metadata only; Skill instructions and "
    "resources are not loaded. Decide whether a Skill helps fulfill the current "
    "user request as part of your normal response. If no Skill applies, answer "
    "directly without any Skill operation or routing decision. When a visible "
    "Skill applies, call skills_activate with its exact skill_version_id before "
    "following that procedure. Do not search to confirm a Skill already visible. "
    "Use skills_search only when it is available and relevant metadata is omitted "
    "from an incomplete catalog. A search result is metadata, not an activation. "
    "Match semantic intent, including equivalent expressions and symbols. Use "
    "Session context to understand the current request, but never activate a Skill "
    "solely because it was installed or used in an earlier Run. Read resources "
    "only when needed. Loaded procedures remain subject to Agent and system "
    "policies and are retained only for the current Agent Run."
)

_KNOWLEDGE_PREAMBLE = (
    "Use the following context when relevant. "
    "If the context is not enough, say you do not know.\n\n"
)


def _messages_with_leading_system_instruction(
    messages: list[Any],
    instruction: str,
) -> list[Any]:
    result = list(messages)
    if result and isinstance(result[0], SystemMessage):
        first = result[0]
        content = first.content
        if isinstance(content, str):
            merged_content = f"{content}\n\n{instruction}"
        elif isinstance(content, list):
            merged_content = [*content, {"type": "text", "text": instruction}]
        else:
            merged_content = instruction
        result[0] = first.model_copy(update={"content": merged_content})
        return result
    return [SystemMessage(content=instruction), *result]


def _messages_with_bound_capability_authority(
    messages: list[Any],
    *,
    has_tools: bool,
    has_skills: bool = False,
) -> list[Any]:
    if not has_tools:
        return list(messages)
    instruction = _BOUND_CAPABILITIES_INSTRUCTION
    if has_skills:
        instruction = instruction.replace(
            "Do not search for, list, discover, or invent additional capabilities.",
            "Installed Skill discovery may be available when explicitly bound by the "
            "runtime, but it never grants additional Tool permissions.",
        )
    return _messages_with_leading_system_instruction(messages, instruction)


def _messages_with_tool_grounding(
    messages: list[Any],
    *,
    has_tools: bool,
) -> list[Any]:
    if not has_tools:
        return list(messages)
    return _messages_with_leading_system_instruction(
        messages,
        _TOOL_GROUNDING_RUNTIME_RULES,
    )


def _messages_with_skill_usage(
    messages: list[Any],
    *,
    has_skills: bool,
) -> list[Any]:
    if not has_skills:
        return list(messages)
    return _messages_with_leading_system_instruction(
        messages,
        _SKILL_USAGE_INSTRUCTION,
    )


def _tool_name(definition: Mapping[str, Any]) -> str | None:
    function = definition.get("function")
    if isinstance(function, Mapping):
        name = function.get("name")
        if isinstance(name, str) and name:
            return name
    name = definition.get("name")
    return name if isinstance(name, str) and name else None


def _apply_replacements(
    messages: list[Any],
    contributions: tuple[ContextManagedContribution, ...],
) -> list[Any]:
    replaced = {
        message_id
        for contribution in contributions
        for message_id in contribution.replaces_message_ids
    }
    if not replaced:
        return list(messages)
    return [
        message
        for message in messages
        if _message_id(message) not in replaced
    ]


def _materialize_contribution(
    contribution: ContextManagedContribution,
) -> SystemMessage:
    source_type = contribution.source_type.strip().upper()
    content = _serialized_content(contribution.content)
    if source_type == "KNOWLEDGE":
        content = f"{_KNOWLEDGE_PREAMBLE}<context>\n{content}\n</context>"

    metadata = {
        **dict(contribution.metadata),
        "source_type": source_type,
        "source_ref": contribution.key,
    }
    metadata.setdefault("selection_method", "context_manager_contribution")
    return SystemMessage(
        content=content,
        additional_kwargs={"woobe_context": metadata},
    )


def _materialize_context_contributions(
    messages: list[Any],
    contributions: tuple[ContextManagedContribution, ...],
) -> list[Any]:
    if not contributions:
        return list(messages)
    materialized = [_materialize_contribution(item) for item in contributions]
    split = 0
    while split < len(messages) and isinstance(messages[split], SystemMessage):
        split += 1
    return [*messages[:split], *materialized, *messages[split:]]


def _prepare_invocation_messages(
    request: ContextAssemblyRequest,
) -> list[Any]:
    active_definitions = tuple(request.environment.active_tool_definitions or ())
    active_names = tuple(
        name
        for definition in active_definitions
        if (name := _tool_name(definition)) is not None
    )
    has_tools = bool(active_definitions)
    has_skills = any(name.startswith("skills_") for name in active_names)

    messages = _apply_replacements(
        list(request.messages),
        request.contributions,
    )
    messages = _messages_with_bound_capability_authority(
        messages,
        has_tools=has_tools,
        has_skills=has_skills,
    )
    messages = _messages_with_skill_usage(
        messages,
        has_skills=has_skills,
    )
    messages = _messages_with_tool_grounding(
        messages,
        has_tools=has_tools,
    )
    return _materialize_context_contributions(
        messages,
        request.contributions,
    )


def _serialized_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _message_id(message: Any) -> str | None:
    value = getattr(message, "id", None)
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


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
    capacity = getattr(request.environment, "model_capacity_units", None)
    capacity = capacity if isinstance(capacity, int) and capacity > 0 else None
    reserved = getattr(request.environment, "reserved_output_units", None)
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


class StandardContextManager:
    """The built-in programmable Standard Context Manager."""

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
        replaced_message_ids = {
            message_id
            for contribution in request.contributions
            for message_id in contribution.replaces_message_ids
        }
        estimated = sum(
            estimate_input_units(
                _serialized_content(getattr(message, "content", ""))
            )
            for message in request.messages
            if _message_id(message) not in replaced_message_ids
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
            message_count=sum(
                1
                for message in request.messages
                if _message_id(message) not in replaced_message_ids
            ),
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
                environment=request.environment,
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
            existing.replaces_message_ids if existing is not None else ()
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
                and _message_id(message) not in already_replaced
            )
        ]
        keep_recent = min(
            self._compaction_keep_recent_messages,
            max(0, request.policy.session.max_messages - 1),
        )
        if len(session_indexes) <= keep_recent:
            return ContextCompactionOutput(
                changed=False,
                metadata={
                    "reason": "session_window_already_compact",
                    "pressure": inspection.pressure,
                },
            )

        compact_indexes = (
            session_indexes
            if keep_recent == 0
            else session_indexes[:-keep_recent]
        )
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

        compact_message_ids = tuple(
            message_id
            for index in compact_indexes
            if (message_id := _message_id(request.messages[index])) is not None
        )
        if len(compact_message_ids) != len(compact_indexes):
            raise RuntimeError(
                "Context Manager compaction requires stable IDs for every replaced message"
            )
        replaced = tuple(sorted(already_replaced.union(compact_message_ids)))

        existing_signatures = (
            existing.metadata.get("covered_message_signatures", ())
            if existing is not None
            else ()
        )
        signature_values = [
            str(value)
            for value in existing_signatures
            if isinstance(value, str) and value
        ]
        signature_values.extend(
            _message_signature(request.messages[index])
            for index in compact_indexes
        )
        covered_signatures = tuple(dict.fromkeys(signature_values))

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
                "covered_message_ids": list(replaced),
                "covered_message_signatures": list(covered_signatures),
            },
            replaces_message_ids=replaced,
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
            messages=_prepare_invocation_messages(request),
            model_invocation_id=request.model_invocation_id,
            agent_run_id=request.agent_run_id,
            project_id=request.project_id,
            provider=request.provider,
            model=request.model,
            environment=request.environment,
            policy=request.policy,
        )


# Legacy class alias; internal code uses StandardContextManager.
StandardContextAssembler = StandardContextManager

__all__ = ["StandardContextManager"]
