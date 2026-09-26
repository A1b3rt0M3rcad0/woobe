from __future__ import annotations

from typing import Any, Callable

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyInvocationContext,
    StrategyModelResult,
    StrategyPhase,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedFallbackModel
from modules.agent.infra.execution.runtime_streaming import emit_runtime_event
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


class RuntimeStrategyModel:
    """Strategy-facing Model facade with runtime instrumentation and conversation ownership."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_initial_phase",
        "_final_model",
        "_final_model_factory",
        "_fallback_model_factory",
        "_tool_definitions",
        "_bound_capabilities",
    )

    def __init__(
        self,
        *,
        capability: ModelInvocationCapability,
        runtime_state: StrategyRuntimeState,
        initial_phase: str,
        final_model: Any | None,
        final_model_factory: Any | None,
        fallback_model_factory: Callable[[], PreparedFallbackModel] | None = None,
        tool_definitions: list[dict[str, Any]] | None = None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._initial_phase = initial_phase
        self._final_model = final_model
        self._final_model_factory = final_model_factory
        self._fallback_model_factory = fallback_model_factory
        self._tool_definitions = list(tool_definitions or [])
        self._bound_capabilities: dict[
            tuple[str, tuple[str, ...]],
            ModelInvocationCapability,
        ] = {}

    def set_fallback_model_factory(
        self,
        factory: Callable[[], PreparedFallbackModel] | None,
    ) -> None:
        self._fallback_model_factory = factory

    @property
    def fallback_available(self) -> bool:
        return self._fallback_model_factory is not None

    def _capability_for_tools(
        self,
        selection: StrategyToolSelection | None,
    ) -> ModelInvocationCapability:
        if not self._tool_definitions:
            return self._capability

        effective = selection
        if effective is None:
            effective = StrategyToolSelection(StrategyToolSelectionMode.ALL)

        if effective.mode is StrategyToolSelectionMode.NONE:
            return self._capability

        if effective.mode is StrategyToolSelectionMode.ALL:
            definitions = list(self._tool_definitions)
        else:
            requested = set(effective.names)
            definitions = []
            resolved: set[str] = set()
            for definition in self._tool_definitions:
                function = definition.get("function")
                name = (
                    function.get("name")
                    if isinstance(function, dict)
                    else definition.get("name")
                )
                if isinstance(name, str) and name in requested:
                    definitions.append(definition)
                    resolved.add(name)
            missing = sorted(requested.difference(resolved))
            if missing:
                raise ValueError(
                    "No model Tool definition is available for selected Tools: "
                    + ", ".join(missing)
                )

        if not definitions:
            return self._capability

        key = (
            effective.mode.value,
            tuple(sorted(effective.names)),
        )
        cached = self._bound_capabilities.get(key)
        if cached is not None:
            return cached

        bind_tools = getattr(self._capability.model, "bind_tools", None)
        if not callable(bind_tools):
            raise RuntimeError(
                "Selected Tools require a model implementation with bind_tools()"
            )
        bound = self._capability.for_model(
            bind_tools(definitions, tool_choice="auto")
        )
        self._bound_capabilities[key] = bound
        return bound

    async def _invoke(
        self,
        *,
        capability: ModelInvocationCapability,
        phase: StrategyPhase,
        context: StrategyInvocationContext,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult:
        call_index = self._runtime_state.next_call_index()
        effective_capability = (
            self._capability_for_tools(tools)
            if capability is self._capability
            else capability
        )
        try:
            result, call = await effective_capability.invoke(
                messages=list(context.messages),
                phase=strategy_phase_value(phase),
                call_index=call_index,
                invocation_id=context.invocation_id,
                context_snapshot=context.snapshot,
                context_prepared=True,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.absorb_model_error(exc)
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=list(execution.llm_calls),
                tool_calls=list(execution.tool_calls),
                knowledge_calls=list(execution.knowledge_calls),
                sources=list(execution.sources),
                timeline=list(execution.timeline),
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=execution.failure_context,
            ) from exc

        self._runtime_state.record_model_call(call)
        self._runtime_state.record_model_message(result)
        return StrategyModelResult(message=result)

    async def invoke(
        self,
        *,
        context: StrategyInvocationContext,
        tools: StrategyToolSelection | None = None,
        phase: StrategyPhase | None = None,
    ) -> StrategyModelResult:
        return await self._invoke(
            capability=self._capability,
            phase=phase or self._initial_phase,
            context=context,
            tools=tools,
        )

    async def invoke_fallback(
        self,
        *,
        context: StrategyInvocationContext,
        primary_error: str,
        phase: StrategyPhase,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult:
        factory = self._fallback_model_factory
        if factory is None:
            raise RuntimeError("Fallback Model is not bound for this Strategy")

        binding = factory()
        info = {
            **binding.metadata,
            "primary_error": primary_error,
        }
        await emit_runtime_event("fallback", **info)
        capability = ModelInvocationCapability(
            model=binding.model,
            provider=binding.provider,
            model_name=binding.model_name,
            pricing_snapshot=binding.pricing_snapshot,
        )
        result = await self._invoke(
            capability=capability,
            phase=phase,
            context=context,
            tools=tools,
        )
        self._runtime_state.execution.fallback_used = True
        self._runtime_state.execution.fallback_info = info
        return result

    async def finalize(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        context: StrategyInvocationContext,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyModelResult:
        terminal_model = self._final_model
        if terminal_model is None and self._final_model_factory is not None:
            terminal_model = self._final_model_factory()
        if terminal_model is None:
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                reason,
                llm_calls=execution.llm_calls,
                tool_calls=execution.tool_calls,
                knowledge_calls=execution.knowledge_calls,
                sources=execution.sources,
                timeline=execution.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context={
                    **(execution.failure_context or {}),
                    "partial_result_available": bool(execution.tool_calls),
                },
            )

        terminal_capability = self._capability.for_model(terminal_model)
        try:
            return await self._invoke(
                capability=terminal_capability,
                phase=phase,
                context=context,
                tools=tools,
            )
        except InstrumentedExecutionError as exc:
            execution = self._runtime_state.execution
            raise InstrumentedExecutionError(
                str(exc),
                llm_calls=execution.llm_calls,
                tool_calls=execution.tool_calls,
                knowledge_calls=execution.knowledge_calls,
                sources=execution.sources,
                timeline=execution.timeline,
                tool_wall_latency_ms=execution.tool_wall_latency_ms,
                tool_call_duration_sum_ms=execution.tool_call_duration_sum_ms,
                failure_context=execution.failure_context,
            ) from exc
