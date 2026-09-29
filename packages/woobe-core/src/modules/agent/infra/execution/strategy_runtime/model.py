from __future__ import annotations

from typing import Any, Callable

from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.strategy_sdk import (
    StrategyExecutionError,
    StrategyInvocation,
    StrategyModelResult,
    StrategyToolCall,
    StrategyToolSelection,
    StrategyToolSelectionMode,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedFallbackModel
from modules.agent.infra.execution.runtime_streaming import emit_runtime_event
from modules.agent.infra.execution.strategy_runtime.invocation import (
    RuntimeStrategyInvocation,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


def _strategy_tool_call(value: object) -> StrategyToolCall | None:
    if not isinstance(value, dict):
        return None
    name = value.get("name")
    if not isinstance(name, str) or not name.strip():
        return None
    args = value.get("args")
    if not isinstance(args, dict):
        args = {}
    call_id = value.get("id")
    return StrategyToolCall(
        id=str(call_id) if call_id is not None else None,
        name=name,
        arguments=args,
    )


def strategy_model_result_from_message(message: Any) -> StrategyModelResult:
    raw_calls = getattr(message, "tool_calls", None) or ()
    tool_calls = tuple(
        call
        for value in raw_calls
        if (call := _strategy_tool_call(value)) is not None
    )
    response_metadata = getattr(message, "response_metadata", None)
    finish_reason = (
        response_metadata.get("finish_reason")
        if isinstance(response_metadata, dict)
        and isinstance(response_metadata.get("finish_reason"), str)
        else None
    )
    return StrategyModelResult(
        content=getattr(message, "content", None),
        tool_calls=tool_calls,
        finish_reason=finish_reason,
    )


def _runtime_invocation(invocation: StrategyInvocation) -> RuntimeStrategyInvocation:
    if not isinstance(invocation, RuntimeStrategyInvocation):
        raise TypeError("Model invocation must be prepared by Strategy Context")
    return invocation


class RuntimeStrategyModel:
    """Strategy-facing Model facade with runtime instrumentation and conversation ownership."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_final_model",
        "_final_model_factory",
        "_fallback_model_factory",
        "_fallback_binding",
        "_structured_repair_model_factory",
        "_tool_definitions",
        "_bound_capabilities",
    )

    def __init__(
        self,
        *,
        capability: ModelInvocationCapability,
        runtime_state: StrategyRuntimeState,
        final_model: Any | None,
        final_model_factory: Any | None,
        fallback_model_factory: Callable[[], PreparedFallbackModel] | None = None,
        structured_repair_model_factory: Callable[[], Any] | None = None,
        tool_definitions: list[dict[str, Any]] | None = None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._final_model = final_model
        self._final_model_factory = final_model_factory
        self._fallback_model_factory = fallback_model_factory
        self._fallback_binding: PreparedFallbackModel | None = None
        self._structured_repair_model_factory = structured_repair_model_factory
        self._tool_definitions = list(tool_definitions or [])
        self._bound_capabilities: dict[str, ModelInvocationCapability] = {}

    @property
    def spec(self):
        spec = self._capability.model_spec
        if spec is None:
            raise RuntimeError("ModelSpec is not bound for this Strategy runtime")
        return spec

    def set_fallback_model_factory(
        self,
        factory: Callable[[], PreparedFallbackModel] | None,
    ) -> None:
        self._fallback_model_factory = factory
        self._fallback_binding = None

    def _resolved_fallback_binding(self) -> PreparedFallbackModel:
        binding = self._fallback_binding
        if binding is not None:
            return binding
        factory = self._fallback_model_factory
        if factory is None:
            raise RuntimeError("Fallback Model is not bound for this Strategy")
        binding = factory()
        self._fallback_binding = binding
        return binding

    def fallback_context_binding(
        self,
    ) -> tuple[str, str, dict[str, Any] | None]:
        binding = self._resolved_fallback_binding()
        return (
            binding.provider,
            binding.model_name,
            binding.pricing_snapshot,
        )

    @property
    def fallback_available(self) -> bool:
        return self._fallback_model_factory is not None

    def _capability_for_tools(
        self,
        selection: StrategyToolSelection,
    ) -> ModelInvocationCapability:
        if not self._tool_definitions:
            return self._capability
        if selection.mode is StrategyToolSelectionMode.NONE:
            return self._capability
        if selection.mode is not StrategyToolSelectionMode.ALL:
            raise ValueError(
                f"Unsupported Tool selection mode: {selection.mode.value}"
            )

        cached = self._bound_capabilities.get(StrategyToolSelectionMode.ALL.value)
        if cached is not None:
            return cached

        bind_tools = getattr(self._capability.model, "bind_tools", None)
        if not callable(bind_tools):
            raise RuntimeError(
                "Authorized Tools require a model implementation with bind_tools()"
            )
        bound = self._capability.for_model(
            bind_tools(list(self._tool_definitions), tool_choice="auto")
        )
        self._bound_capabilities[StrategyToolSelectionMode.ALL.value] = bound
        return bound

    async def _invoke(
        self,
        *,
        capability: ModelInvocationCapability,
        invocation: RuntimeStrategyInvocation,
        record_message: bool = True,
        retain_terminal_result: bool = False,
    ) -> StrategyModelResult:
        call_index = self._runtime_state.next_call_index()
        effective_capability = (
            self._capability_for_tools(invocation.tools)
            if capability is self._capability
            else capability
        )
        try:
            result, call = await effective_capability.invoke(
                messages=list(invocation.messages),
                phase=invocation.phase,
                call_index=call_index,
                invocation_id=invocation.invocation_id,
                context_snapshot=invocation.snapshot,
                context_prepared=True,
            )
        except InstrumentedExecutionError as exc:
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

        self._runtime_state.record_model_call(call)
        if record_message:
            self._runtime_state.record_model_message(result)
        elif retain_terminal_result:
            self._runtime_state.last_model_message = result
            self._runtime_state.execution.result = result
        return strategy_model_result_from_message(result)

    async def invoke_auxiliary(
        self,
        invocation: RuntimeStrategyInvocation,
    ) -> StrategyModelResult:
        """Run a Runtime-requested auxiliary Model call without extending chat history."""

        return await self._invoke(
            capability=self._capability,
            invocation=invocation,
            record_message=False,
        )

    async def invoke(
        self,
        invocation: StrategyInvocation,
    ) -> StrategyModelResult:
        return await self._invoke(
            capability=self._capability,
            invocation=_runtime_invocation(invocation),
        )

    async def invoke_structured_repair(
        self,
        invocation: RuntimeStrategyInvocation,
    ) -> StrategyModelResult:
        """Execute structured-output repair through the Model boundary."""

        factory = self._structured_repair_model_factory
        if factory is None:
            raise RuntimeError("Structured repair Model is not bound for this Strategy")
        capability = self._capability.for_model(factory())
        return await self._invoke(
            capability=capability,
            invocation=invocation,
            record_message=False,
            retain_terminal_result=True,
        )

    async def invoke_fallback(
        self,
        invocation: StrategyInvocation,
        *,
        primary_error: str,
    ) -> StrategyModelResult:
        runtime_invocation = _runtime_invocation(invocation)
        binding = self._resolved_fallback_binding()
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
            invocation=runtime_invocation,
        )
        self._runtime_state.execution.fallback_used = True
        self._runtime_state.execution.fallback_info = info
        return result

    async def finalize(
        self,
        invocation: StrategyInvocation,
        *,
        reason: str,
    ) -> StrategyModelResult:
        runtime_invocation = _runtime_invocation(invocation)
        terminal_model = self._final_model
        if terminal_model is None and self._final_model_factory is not None:
            terminal_model = self._final_model_factory()
        if terminal_model is None:
            execution = self._runtime_state.execution
            runtime_error = InstrumentedExecutionError(
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
            raise StrategyExecutionError(reason) from runtime_error

        terminal_capability = self._capability.for_model(terminal_model)
        return await self._invoke(
            capability=terminal_capability,
            invocation=runtime_invocation,
        )
