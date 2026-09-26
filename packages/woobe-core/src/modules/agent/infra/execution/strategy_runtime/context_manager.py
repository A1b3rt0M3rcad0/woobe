from __future__ import annotations

import json
from typing import Any

from langchain_core.messages import SystemMessage

from modules.agent.application.strategy_sdk import (
    StrategyContextContribution,
    StrategyInvocationContext,
    StrategyPhase,
    StrategyToolSelection,
    strategy_phase_value,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


_KNOWLEDGE_PREAMBLE = (
    "Use the following context when relevant. "
    "If the context is not enough, say you do not know.\n\n"
)


def _serialized_content(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except (TypeError, ValueError):
        return str(value)


def _materialize_contribution(
    contribution: StrategyContextContribution,
) -> SystemMessage:
    source_type = contribution.source_type.strip().upper()
    content = _serialized_content(contribution.content)
    if source_type == "KNOWLEDGE":
        content = f"{_KNOWLEDGE_PREAMBLE}<context>\n{content}\n</context>"

    metadata = {
        **dict(contribution.metadata),
        "source_type": source_type,
        "source_ref": contribution.key,
        "selection_method": "strategy_context_contribution",
    }
    return SystemMessage(
        content=content,
        additional_kwargs={"woobe_context": metadata},
    )


def _with_contributions(
    messages: list[Any],
    contributions: tuple[StrategyContextContribution, ...],
) -> list[Any]:
    if not contributions:
        return list(messages)
    materialized = [_materialize_contribution(item) for item in contributions]
    split = 0
    while split < len(messages) and isinstance(messages[split], SystemMessage):
        split += 1
    return [*messages[:split], *materialized, *messages[split:]]


class RuntimeStrategyContextManager:
    """Strategy-facing Context facade with runtime-owned contribution storage."""

    __slots__ = ("_capability", "_runtime_state")

    def __init__(
        self,
        *,
        capability: ContextAssemblyCapability,
        runtime_state: StrategyRuntimeState,
    ) -> None:
        self._capability = capability
        self._runtime_state = runtime_state

    def has(self, key: str) -> bool:
        return key in self._runtime_state.context_contributions

    def set(self, contribution: StrategyContextContribution) -> None:
        key = contribution.key.strip()
        if not key:
            raise ValueError("Context contribution key must not be empty")
        self._runtime_state.context_contributions[key] = contribution

    def remove(self, key: str) -> None:
        self._runtime_state.context_contributions.pop(key, None)

    async def assemble(
        self,
        *,
        phase: StrategyPhase | None = None,
        tools: StrategyToolSelection | None = None,
    ) -> StrategyInvocationContext:
        contributions = tuple(
            contribution
            for contribution in self._runtime_state.context_contributions.values()
            if isinstance(contribution, StrategyContextContribution)
        )
        messages = _with_contributions(
            self._runtime_state.messages,
            contributions,
        )
        result = self._capability.assemble(
            messages=messages,
            phase=strategy_phase_value(phase or "response_generation"),
            tool_selection_mode=tools.mode.value if tools is not None else None,
            tool_selection_names=tools.names if tools is not None else (),
        )
        return StrategyInvocationContext(
            invocation_id=result.invocation_id,
            messages=result.messages,
            snapshot=result.snapshot,
        )
