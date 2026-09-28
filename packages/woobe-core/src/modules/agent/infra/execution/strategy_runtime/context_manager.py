from __future__ import annotations

from typing import Any, Protocol

import uuid6
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.interfaces.context_manager import (
    ContextManagedContribution,
    ContextManagerCapabilities,
    ContextSummaryOutput,
    ContextSummaryRequest,
)
from modules.agent.application.interfaces.execution import InstrumentedExecutionError
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.application.strategy_sdk import (
    StrategyContextCompactionResult,
    StrategyContextContribution,
    StrategyExecutionError,
    StrategyContextInspection,
    StrategyContextTarget,
    StrategyKnowledgeResult,
    StrategyPhase,
    StrategyToolSelection,
    StrategyToolSelectionMode,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.message_progression import (
    terminal_response_messages,
)
from modules.agent.infra.execution.strategy_runtime.invocation import (
    RuntimeStrategyInvocation,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class _ContextModelCapabilities(Protocol):
    """Minimal Model surface available to Context Manager runtime mechanics."""

    @property
    def fallback_available(self) -> bool: ...

    async def invoke_auxiliary(
        self,
        invocation: RuntimeStrategyInvocation,
    ) -> Any: ...

    def fallback_context_binding(
        self,
    ) -> tuple[str, str, dict[str, Any] | None]: ...


class _RuntimeContextManagerCapabilities(ContextManagerCapabilities):
    """Runtime mechanisms available to the configured Context Manager."""

    __slots__ = ("_model_capabilities",)

    def __init__(self, model_capabilities: _ContextModelCapabilities) -> None:
        self._model_capabilities = model_capabilities

    async def summarize(
        self,
        request: ContextSummaryRequest,
    ) -> ContextSummaryOutput:
        if request.target_units <= 0:
            raise ValueError("Context summary target_units must be positive")

        no_tools = StrategyToolSelection(StrategyToolSelectionMode.NONE)
        invocation = RuntimeStrategyInvocation(
            invocation_id=uuid6.uuid7(),
            phase=request.phase,
            tools=no_tools,
            messages=(
                SystemMessage(content=request.instruction),
                HumanMessage(content=request.input_text),
            ),
            snapshot=None,
        )
        result = await self._model_capabilities.invoke_auxiliary(invocation)
        content = result.content
        if not isinstance(content, str) or not content.strip():
            raise RuntimeError("Context Manager summarization returned no textual content")
        return ContextSummaryOutput(
            content=content,
            metadata={
                "mechanism": "model_summary",
                "target_units": request.target_units,
            },
        )


class RuntimeStrategyContextManager:
    """Execution-facing facade over the frozen programmable Context Manager."""

    __slots__ = (
        "_capability",
        "_runtime_state",
        "_base_messages",
        "_final_json_instruction",
        "_model_capabilities",
    )

    def __init__(
        self,
        *,
        capability: ContextAssemblyCapability,
        runtime_state: StrategyRuntimeState,
        base_messages: list[Any] | None = None,
        final_json_instruction: str | None = None,
        model_capabilities: _ContextModelCapabilities | None = None,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state
        self._base_messages = list(base_messages or runtime_state.messages)
        self._final_json_instruction = final_json_instruction
        self._model_capabilities = model_capabilities
        self._sync_execution_context()

    def _sync_execution_context(self) -> None:
        execution_context = current_execution.get()
        if execution_context is not None:
            execution_context.strategy_context_contributions = dict(
                self._runtime_state.context_contributions
            )

    def has(self, key: str) -> bool:
        return key in self._runtime_state.context_contributions

    def set(self, contribution: StrategyContextContribution) -> None:
        key = contribution.key.strip()
        if not key:
            raise ValueError("Context contribution key must not be empty")
        self._runtime_state.context_contributions[key] = contribution
        self._runtime_state.context_replacements.pop(key, None)
        self._sync_execution_context()

    def remove(self, key: str) -> None:
        self._runtime_state.context_contributions.pop(key, None)
        self._runtime_state.context_replacements.pop(key, None)
        self._sync_execution_context()

    def include_knowledge(self, result: StrategyKnowledgeResult) -> None:
        if not result.found:
            self.remove("knowledge.primary")
            return
        self.set(
            StrategyContextContribution(
                key="knowledge.primary",
                source_type="KNOWLEDGE",
                content=result.content,
                metadata={
                    "query": result.query,
                    "retrieval": dict(result.metadata),
                    "sources": [
                        source.as_dict()
                        for source in result.sources
                    ],
                },
            )
        )

    def _contributions(self) -> tuple[StrategyContextContribution, ...]:
        return tuple(
            contribution
            for contribution in self._runtime_state.context_contributions.values()
            if isinstance(contribution, StrategyContextContribution)
        )

    def _managed_contributions(self) -> tuple[ContextManagedContribution, ...]:
        return tuple(
            ContextManagedContribution(
                key=item.key,
                source_type=item.source_type,
                content=item.content,
                metadata=dict(item.metadata),
                replaces_message_ids=self._runtime_state.context_replacements.get(
                    item.key,
                    (),
                ),
            )
            for item in self._contributions()
        )

    def inspect(self) -> StrategyContextInspection:
        result = self._capability.inspect(
            messages=list(self._runtime_state.messages),
            contributions=self._managed_contributions(),
        )
        return StrategyContextInspection(
            message_count=result.message_count,
            contribution_count=result.contribution_count,
            estimated_input_units=result.estimated_input_units,
            usable_input_units=result.usable_input_units,
            utilization=result.utilization,
            pressure=result.pressure,
        )

    async def compact(
        self,
        *,
        phase: StrategyPhase | None = None,
    ) -> StrategyContextCompactionResult:
        if self._model_capabilities is None:
            raise RuntimeError("Context Manager Model capabilities are not bound")

        result = await self._capability.compact(
            messages=list(self._runtime_state.messages),
            contributions=self._managed_contributions(),
            phase=strategy_phase_value(phase or "context_compaction"),
            capabilities=_RuntimeContextManagerCapabilities(self._model_capabilities),
        )
        for key in result.remove_keys:
            self._runtime_state.context_contributions.pop(key, None)
            self._runtime_state.context_replacements.pop(key, None)

        upserted: list[str] = []
        for item in result.upserts:
            contribution = StrategyContextContribution(
                key=item.key,
                source_type=item.source_type,
                content=item.content,
                metadata=dict(item.metadata),
            )
            self._runtime_state.context_contributions[item.key] = contribution
            self._runtime_state.context_replacements[item.key] = (
                item.replaces_message_ids
            )
            upserted.append(item.key)

        if result.changed or result.remove_keys or result.upserts:
            self._sync_execution_context()

        return StrategyContextCompactionResult(
            changed=result.changed,
            upserted_keys=tuple(upserted),
            removed_keys=tuple(result.remove_keys),
            metadata=dict(result.metadata),
        )

    async def _assemble_messages(
        self,
        *,
        messages: list[Any],
        phase: StrategyPhase,
        tools: StrategyToolSelection | None,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
        include_contributions: bool = True,
        include_skill_context: bool = True,
    ) -> RuntimeStrategyInvocation:
        capability = self._capability
        if target is StrategyContextTarget.FALLBACK:
            if self._model_capabilities is None or not self._model_capabilities.fallback_available:
                raise RuntimeError("Fallback Context requested without a bound fallback Model")
            if (
                tools is not None
                and tools.mode is not StrategyToolSelectionMode.NONE
            ):
                raise ValueError("Fallback Context currently requires tools=ctx.tools.none()")
            provider, model_name, pricing_snapshot = (
                self._model_capabilities.fallback_context_binding()
            )
            capability = ContextAssemblyCapability(
                manager=self._capability.manager,
                provider=provider,
                model_name=model_name,
                pricing_snapshot=pricing_snapshot,
                tool_definitions=(),
            )

        contributions = (
            self._managed_contributions()
            if include_contributions
            else ()
        )
        next_call_index = self._runtime_state.call_index + 1
        try:
            result = capability.assemble(
                messages=list(messages),
                phase=strategy_phase_value(phase),
                contributions=contributions,
                tool_selection_mode=(
                    tools.mode.value
                    if tools is not None
                    else StrategyToolSelectionMode.ALL.value
                ),
                include_skill_context=include_skill_context,
                call_index=next_call_index,
            )
        except InstrumentedExecutionError as exc:
            self._runtime_state.call_index = next_call_index
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

        return RuntimeStrategyInvocation(
            invocation_id=result.invocation_id,
            phase=strategy_phase_value(phase),
            tools=tools or StrategyToolSelection(StrategyToolSelectionMode.ALL),
            messages=result.messages,
            snapshot=result.snapshot,
        )

    async def prepare(
        self,
        *,
        tools: StrategyToolSelection,
        phase: StrategyPhase | None = None,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> RuntimeStrategyInvocation:
        return await self._assemble_messages(
            messages=list(self._runtime_state.messages),
            phase=phase or "response_generation",
            tools=tools,
            target=target,
        )

    async def prepare_final(
        self,
        *,
        reason: str,
        phase: StrategyPhase,
        tools: StrategyToolSelection,
        target: StrategyContextTarget = StrategyContextTarget.PRIMARY,
    ) -> RuntimeStrategyInvocation:
        messages = terminal_response_messages(
            list(self._base_messages),
            self._final_json_instruction,
            self._runtime_state.execution.tool_calls,
            reason,
        )
        return await self._assemble_messages(
            messages=messages,
            phase=phase,
            tools=tools,
            target=target,
        )
