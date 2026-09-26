from __future__ import annotations

import json
from typing import Any

from modules.agent.application.strategy_sdk import StrategyModelResult, StrategyPhase
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.preparation import PreparedExecution
from modules.agent.infra.execution.structured_json_repair import repair_json_if_needed
from modules.agent.infra.execution.strategy_runtime.runtime_state import StrategyRuntimeState


class RuntimeStrategyOutput:
    """Strategy-facing output facade; it never runs unless the Strategy calls it."""

    __slots__ = (
        "_runtime_state",
        "_json_enabled",
        "_schema",
        "_llm_factory",
        "_provider",
        "_model_name",
        "_api_key",
        "_base_url",
        "_max_tokens",
        "_clean_json_answer",
        "_pricing_snapshot",
        "_context_capability",
    )

    def __init__(
        self,
        *,
        runtime_state: StrategyRuntimeState,
        json_enabled: bool,
        schema: dict[str, Any] | None = None,
        llm_factory: Any | None = None,
        provider: str = "",
        model_name: str = "",
        api_key: str = "",
        base_url: str | None = None,
        max_tokens: int = 1000,
        clean_json_answer: Any | None = None,
        pricing_snapshot: dict[str, Any] | None = None,
        context_capability: ContextAssemblyCapability | None = None,
    ) -> None:
        self._runtime_state = runtime_state
        self._json_enabled = json_enabled
        self._schema = dict(schema or {})
        self._llm_factory = llm_factory
        self._provider = provider
        self._model_name = model_name
        self._api_key = api_key
        self._base_url = base_url
        self._max_tokens = max_tokens
        self._clean_json_answer = clean_json_answer
        self._pricing_snapshot = pricing_snapshot
        self._context_capability = context_capability

    @classmethod
    def disabled(cls, *, runtime_state: StrategyRuntimeState) -> "RuntimeStrategyOutput":
        return cls(runtime_state=runtime_state, json_enabled=False)

    @classmethod
    def from_prepared(
        cls,
        *,
        prepared: PreparedExecution,
        runtime_state: StrategyRuntimeState,
    ) -> "RuntimeStrategyOutput":
        return cls(
            runtime_state=runtime_state,
            json_enabled=prepared.json_enabled,
            schema=prepared.response_schema,
            llm_factory=prepared.llm_factory,
            provider=prepared.provider,
            model_name=prepared.model_name,
            api_key=prepared.api_key,
            base_url=prepared.base_url,
            max_tokens=prepared.effective_output_tokens,
            clean_json_answer=prepared.clean_json_answer,
            pricing_snapshot=prepared.pricing_snapshot,
            context_capability=ContextAssemblyCapability(
                assembler=prepared.context_assembler,
                provider=prepared.provider,
                model_name=prepared.model_name,
                pricing_snapshot=prepared.pricing_snapshot,
            ),
        )

    @property
    def json_required(self) -> bool:
        return self._json_enabled

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

    async def repair(
        self,
        result: StrategyModelResult,
        *,
        phase: StrategyPhase,
    ) -> StrategyModelResult:
        if not self._json_enabled:
            return result
        if self._llm_factory is None or self._context_capability is None:
            raise RuntimeError("Structured output repair is not bound for this Strategy")

        execution = self._runtime_state.execution
        execution.result = result.message
        repaired = await repair_json_if_needed(
            execution=execution,
            call_index=self._runtime_state.call_index,
            llm_factory=self._llm_factory,
            provider=self._provider,
            model_name=self._model_name,
            api_key=self._api_key,
            base_url=self._base_url,
            max_tokens=self._max_tokens,
            schema=self._schema,
            clean_json_answer=self._clean_json_answer or (lambda value: value),
            pricing_snapshot=self._pricing_snapshot,
            context_capability=self._context_capability,
        )
        if repaired.llm_calls:
            self._runtime_state.call_index = max(
                self._runtime_state.call_index,
                int(repaired.llm_calls[-1].get("call_index") or 0),
            )
        return StrategyModelResult(message=repaired.result)
