from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import uuid6

from modules.agent.application.interfaces.context_assembler import (
    ContextAssembler,
    ContextAssemblyRequest,
    ContextBudgetExceeded,
    ContextCompactionOutput,
    ContextCompactionRequest,
    ContextInspectionOutput,
    ContextInspectionRequest,
    ContextManagedContribution,
    ContextManagerCapabilities,
)
from modules.agent.application.interfaces.context_policy import ContextPolicyV1
from modules.agent.application.interfaces.execution import (
    InstrumentedExecution,
    InstrumentedExecutionError,
)
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.execution_instrumentation import utc_iso


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


def _pricing_evidence(pricing_snapshot: dict[str, Any] | None) -> dict[str, Any]:
    if not pricing_snapshot:
        return {
            "provider_model_id": None,
            "provider_credential_id": None,
            "pricing_id": None,
            "pricing_snapshot": None,
        }
    return {
        "provider_model_id": pricing_snapshot.get("provider_model_id"),
        "provider_credential_id": pricing_snapshot.get("provider_credential_id"),
        "pricing_id": pricing_snapshot.get("pricing_id"),
        "pricing_snapshot": pricing_snapshot,
    }


def _record_live_context_failure(call: dict[str, Any]) -> None:
    context = current_execution.get()
    execution = getattr(context, "execution", None) if context is not None else None
    if not isinstance(execution, InstrumentedExecution):
        return

    call_id = call.get("call_id")
    if call_id and any(
        item.get("call_id") == call_id for item in execution.llm_calls
    ):
        return
    execution.llm_calls.append(call)
    execution.timeline.append(
        {"kind": "llm", "occurred_at": call["occurred_at"], "payload": call}
    )
    execution.failure_context = {
        key: value
        for key, value in call.items()
        if key
        in {
            "phase",
            "call_index",
            "provider",
            "model",
            "code",
            "context_fit_status",
            "configured_budget_units",
            "effective_budget_units",
            "mandatory_units",
            "model_capacity_units",
            "reserved_output_units",
            "runtime_reserve_units",
            "provider_called",
        }
    }


def _context_budget_error(
    exc: ContextBudgetExceeded,
    *,
    invocation_id: UUID,
    phase: str,
    call_index: int,
    provider: str,
    model_name: str,
    pricing_snapshot: dict[str, Any] | None,
    started_at: str,
    started: float,
) -> InstrumentedExecutionError:
    ended_at = utc_iso()
    failure_context = {
        "phase": phase,
        "call_index": call_index,
        "provider": provider,
        "model": model_name,
        **exc.failure_context(),
    }
    call = {
        "call_id": str(invocation_id),
        "call_index": call_index,
        "phase": phase,
        "status": "error",
        "error": str(exc),
        "started_at": started_at,
        "ended_at": ended_at,
        "occurred_at": ended_at,
        "latency_ms": round((time.monotonic() - started) * 1000),
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "cost_usd": None,
        "cost_status": "unknown_tokens",
        "cost_reason": (
            "Model invocation was blocked by Context Budget before provider execution"
        ),
        "usage_complete": False,
        "provider": provider,
        "model": model_name,
        "context_snapshot": None,
        **_pricing_evidence(pricing_snapshot),
        **failure_context,
    }
    _record_live_context_failure(call)
    return InstrumentedExecutionError(
        str(exc),
        llm_calls=[call],
        timeline=[{"kind": "llm", "occurred_at": ended_at, "payload": call}],
        failure_context=failure_context,
    )


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

    def inspect(
        self,
        *,
        messages: list[Any],
        contributions: tuple[ContextManagedContribution, ...],
    ) -> ContextInspectionOutput:
        context = current_execution.get()
        if context is None or self.assembler is None:
            return ContextInspectionOutput(
                message_count=len(messages),
                contribution_count=len(contributions),
                estimated_input_units=0,
                usable_input_units=None,
                utilization=None,
                pressure="UNKNOWN",
            )
        policy = ContextPolicyV1.model_validate(context.context_policy or {})
        return self.assembler.inspect(
            ContextInspectionRequest(
                messages=tuple(messages),
                contributions=contributions,
                runtime_context=context,
                policy=policy,
            )
        )

    async def compact(
        self,
        *,
        messages: list[Any],
        contributions: tuple[ContextManagedContribution, ...],
        phase: str,
        capabilities: ContextManagerCapabilities,
    ) -> ContextCompactionOutput:
        context = current_execution.get()
        if context is None or self.assembler is None:
            return ContextCompactionOutput(
                changed=False,
                metadata={"reason": "context_manager_unavailable"},
            )
        policy = ContextPolicyV1.model_validate(context.context_policy or {})
        return await self.assembler.compact(
            ContextCompactionRequest(
                messages=tuple(messages),
                contributions=contributions,
                phase=phase,
                runtime_context=context,
                policy=policy,
            ),
            capabilities,
        )

    def active_tool_definitions(
        self,
        mode: str | None,
    ) -> list[dict[str, Any]] | None:
        if mode is None:
            return None
        if mode == "none":
            return []
        if mode != "all":
            raise ValueError(f"Unsupported Tool selection mode: {mode}")
        if not self.tool_definitions:
            # Compatibility callers may provide an already-bound model without
            # the original definitions. Preserve the runtime's existing Tool
            # metadata instead of interpreting that as an explicit empty set.
            return None
        return [dict(definition) for definition in self.tool_definitions]

    def assemble(
        self,
        *,
        messages: list[Any],
        phase: str,
        tool_selection_mode: str | None = None,
        invocation_id: UUID | None = None,
        call_index: int | None = None,
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

        live_execution = getattr(context, "execution", None)
        resolved_call_index = call_index
        if resolved_call_index is None:
            resolved_call_index = (
                len(live_execution.llm_calls) + 1
                if isinstance(live_execution, InstrumentedExecution)
                else 1
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
        selected_tools = self.active_tool_definitions(tool_selection_mode)
        if selected_tools is not None:
            context.active_tool_definitions = selected_tools
        elif phase in {"final_response_generation", "json_repair"}:
            context.active_tool_definitions = []

        started_at = utc_iso()
        started = time.monotonic()
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
        except ContextBudgetExceeded as exc:
            raise _context_budget_error(
                exc,
                invocation_id=resolved_invocation_id,
                phase=phase,
                call_index=resolved_call_index,
                provider=self.provider,
                model_name=self.model_name,
                pricing_snapshot=self.pricing_snapshot,
                started_at=started_at,
                started=started,
            ) from exc
        finally:
            context.model_capacity_units = previous_capacity
            context.reserved_output_units = previous_reserved
            context.active_tool_definitions = previous_tools
