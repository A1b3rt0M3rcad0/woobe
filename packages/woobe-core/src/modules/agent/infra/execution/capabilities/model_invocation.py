from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.infra.execution.durable_execution_instrumentation import invoke_llm


@dataclass(frozen=True, slots=True)
class ModelInvocationCapability:
    """Durable, instrumented access to one model bound for this execution."""

    model: Any
    provider: str
    model_name: str
    pricing_snapshot: dict[str, Any] | None = None
    context_assembler: ContextAssembler | None = None

    async def invoke(
        self,
        *,
        messages: list,
        phase: str,
        call_index: int,
    ) -> tuple[Any, dict[str, Any]]:
        return await invoke_llm(
            model=self.model,
            messages=messages,
            phase=phase,
            call_index=call_index,
            provider=self.provider,
            model_name=self.model_name,
            pricing_snapshot=self.pricing_snapshot,
            context_assembler=self.context_assembler,
        )
