from __future__ import annotations

import json
from typing import Any, Protocol

from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyExecutionError,
    StrategyModelResult,
    StrategyPhase,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    strategy_phase_value,
)
from modules.agent.application.strategy_sdk.output import (
    model_result_has_public_output,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedExecution
from modules.agent.infra.execution.strategy_runtime.invocation import (
    RuntimeStrategyInvocation,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


class _OutputModelCapabilities(Protocol):
    """Minimal Model mechanism available to Output repair."""

    async def invoke_structured_repair(
        self,
        invocation: RuntimeStrategyInvocation,
    ) -> StrategyModelResult: ...


class RuntimeStrategyOutput:
    """Strategy-facing output policy; Model execution remains owned by Model Runtime."""

    __slots__ = (
        "_runtime_state",
        "_json_enabled",
        "_schema",
        "_clean_json_answer",
        "_context_capability",
        "_model_capabilities",
    )

    def __init__(
        self,
        *,
        runtime_state: StrategyRuntimeState,
        json_enabled: bool,
        schema: dict[str, Any] | None = None,
        clean_json_answer: Any | None = None,
        context_capability: ContextAssemblyCapability | None = None,
        model_capabilities: _OutputModelCapabilities | None = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._json_enabled = json_enabled
        self._schema = dict(schema or {})
        self._clean_json_answer = clean_json_answer
        self._context_capability = context_capability
        self._model_capabilities = model_capabilities

    @classmethod
    def disabled(cls, *, runtime_state: StrategyRuntimeState) -> "RuntimeStrategyOutput":
        return cls(runtime_state=runtime_state, json_enabled=False)

    @classmethod
    def from_prepared(
        cls,
        *,
        prepared: PreparedExecution,
        runtime_state: StrategyRuntimeState,
        context_capability: ContextAssemblyCapability,
        model_capabilities: _OutputModelCapabilities,
    ) -> "RuntimeStrategyOutput":
        return cls(
            runtime_state=runtime_state,
            json_enabled=prepared.json_enabled,
            schema=prepared.response_schema,
            clean_json_answer=prepared.clean_json_answer,
            context_capability=context_capability,
            model_capabilities=model_capabilities,
        )

    @property
    def json_required(self) -> bool:
        return self._json_enabled

    def has_public_output(self, result: StrategyModelResult) -> bool:
        return model_result_has_public_output(result)

    def requires_repair(self, result: StrategyModelResult) -> bool:
        if not self._json_enabled:
            return False
        answer = result.content
        if not isinstance(answer, str):
            answer = str(answer)
        clean = self._clean_json_answer or (lambda value: value)
        try:
            json.loads(clean(answer))
            return False
        except Exception:
            return True

    def _raise_context_error(self, exc: InstrumentedExecutionError) -> None:
        self._runtime_state.absorb_model_error(exc)
        execution = self._runtime_state.execution
        runtime_error = InstrumentedExecutionError(
            str(exc),
            llm_calls=list(execution.llm_calls),
            tool_calls=list(execution.tool_calls),
            knowledge_calls=list(execution.knowledge_calls),
            sources=list(execution.sources),
            timeline=list(execution.timeline),
            tool_wall_latency_ms=execution.tool_wall_latency_ms,
            tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
            failure_context=execution.failure_context,
        )
        raise StrategyExecutionError(str(exc)) from runtime_error

    async def repair(
        self,
        result: StrategyModelResult,
        *,
        phase: StrategyPhase,
    ) -> StrategyModelResult:
        if not self._json_enabled:
            return result
        if self._context_capability is None or self._model_capabilities is None:
            raise RuntimeError("Structured output repair is not bound for this Strategy")

        answer = result.content
        if not isinstance(answer, str):
            answer = str(answer)
        schema_json = json.dumps(self._schema, indent=2)
        repair_messages = [
            SystemMessage(
                content=(
                    "Repair the answer into valid JSON matching the schema. "
                    "Return JSON only.\n"
                    f"<schema>\n{schema_json}\n</schema>"
                )
            ),
            HumanMessage(content=answer),
        ]
        normalized_phase = strategy_phase_value(phase)
        next_call_index = self._runtime_state.call_index + 1
        try:
            assembled = self._context_capability.assemble(
                messages=repair_messages,
                phase=normalized_phase,
                tool_selection_mode=StrategyToolSelectionMode.NONE.value,
                call_index=next_call_index,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.call_index = next_call_index
            self._raise_context_error(exc)
            raise AssertionError("unreachable")

        invocation = RuntimeStrategyInvocation(
            invocation_id=assembled.invocation_id,
            phase=normalized_phase,
            tools=StrategyToolSelection(StrategyToolSelectionMode.NONE),
            messages=assembled.messages,
            snapshot=assembled.snapshot,
        )
        return await self._model_capabilities.invoke_structured_repair(invocation)
