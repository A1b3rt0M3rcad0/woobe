from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import uuid6

from modules.agent.application.context_policy import ContextPolicyV1
from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyRequest,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.strategy_sdk import (
    StrategyToolSelection,
    StrategyToolSelectionMode,
)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    if isinstance(value, str) and value.strip().isdigit():
        parsed = int(value)
        return parsed if parsed > 0 else None
    return None


def _effective_output_tokens(
    configured: Any,
    pricing_snapshot: dict[str, Any] | None,
    *,
    default: int = 1000,
) -> int:
    desired = _positive_int(configured) or default
    model_limit = _positive_int((pricing_snapshot or {}).get("max_output_tokens"))
    return min(desired, model_limit) if model_limit is not None else desired


def _tool_definition_name(definition: dict[str, Any]) -> str | None:
    function = definition.get("function")
    if isinstance(function, dict):
        name = function.get("name")
        if isinstance(name, str) and name:
            return name
    name = definition.get("name")
    return name if isinstance(name, str) and name else None


@dataclass(frozen=True, slots=True)
class ContextAssemblyResult:
    invocation_id: UUID
    messages: tuple[Any, ...]
    snapshot: Any | None


@dataclass(frozen=True, slots=True)
class ContextAssemblyCapability:
    """Materialize one invocation Context through the frozen Context Manager."""

    assembler: ContextAssembler | None
    provider: str
    model_name: str
    pricing_snapshot: dict[str, Any] | None
    tool_definitions: tuple[dict[str, Any], ...] = ()

    def _selected_tool_definitions(
        self,
        selection: StrategyToolSelection | None,
    ) -> list[dict[str, Any]] | None:
        if selection is None:
            return None
        if selection.mode is StrategyToolSelectionMode.NONE:
            return []
        if selection.mode is StrategyToolSelectionMode.ALL:
            return [dict(definition) for definition in self.tool_definitions]

        requested = set(selection.names)
        selected = [
            dict(definition)
            for definition in self.tool_definitions
            if _tool_definition_name(definition) in requested
        ]
        resolved = {
            name
            for definition in selected
            if (name := _tool_definition_name(definition)) is not None
        }
        missing = sorted(requested.difference(resolved))
        if missing:
            raise ValueError(
                "No model Tool definition is available for selected Tools: "
                + ", ".join(missing)
            )
        return selected

    def assemble(
        self,
        *,
        messages: list[Any],
        phase: str,
        tools: StrategyToolSelection | None = None,
        invocation_id: UUID | None = None,
    ) -> ContextAssemblyResult:
        resolved_invocation_id = invocation_id or uuid6.uuid7()
        context = current_execution.get()
        if context is None or context.run_id is None or context.project_id is None:
            return ContextAssemblyResult(
                invocation_id=resolved_invocation_id,
                messages=tuple(messages),
                snapshot=None,
            )
        if self.assembler is None:
            raise RuntimeError(
                "ContextAssembler dependency is required for instrumented Agent execution"
            )

        policy = ContextPolicyV1.model_validate(context.context_policy or {})
        previous_capacity = context.model_capacity_units
        previous_reserved = context.reserved_output_units
        previous_tools = context.active_tool_definitions

        context.model_capacity_units = _positive_int(
            (self.pricing_snapshot or {}).get("context_window")
        )
        context.reserved_output_units = _effective_output_tokens(
            previous_reserved,
            self.pricing_snapshot,
        )
        selected_tools = self._selected_tool_definitions(tools)
        if selected_tools is not None:
            context.active_tool_definitions = selected_tools
        elif phase in {"final_response_generation", "json_repair"}:
            context.active_tool_definitions = []

        try:
            assembled = self.assembler.assemble(
                ContextAssemblyRequest(
                    messages=messages,
                    model_invocation_id=resolved_invocation_id,
                    agent_run_id=context.run_id,
                    project_id=context.project_id,
                    provider=self.provider,
                    model=self.model_name,
                    runtime_context=context,
                    policy=policy,
                )
            )
            return ContextAssemblyResult(
                invocation_id=resolved_invocation_id,
                messages=tuple(assembled.messages),
                snapshot=assembled.snapshot,
            )
        finally:
            context.model_capacity_units = previous_capacity
            context.reserved_output_units = previous_reserved
            context.active_tool_definitions = previous_tools
