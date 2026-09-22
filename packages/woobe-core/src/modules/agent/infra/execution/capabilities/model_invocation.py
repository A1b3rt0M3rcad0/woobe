from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable

from modules.agent.application.interfaces.context_assembler import ContextAssembler
from modules.agent.infra.execution.durable_execution_instrumentation import invoke_llm

ModelInvokeFn = Callable[..., Awaitable[tuple[Any, dict[str, Any]]]]


@dataclass(frozen=True, slots=True)
class ModelInvocationCapability:
    """Durable, instrumented access to one model bound for this execution."""

    model: Any
    provider: str
    model_name: str
    pricing_snapshot: dict[str, Any] | None = None
    context_assembler: ContextAssembler | None = None
    invoke_fn: ModelInvokeFn | None = None

    def for_model(self, model: Any) -> ModelInvocationCapability:
        """Reuse the same runtime guarantees with a different prepared model instance."""
        return ModelInvocationCapability(
            model=model,
            provider=self.provider,
            model_name=self.model_name,
            pricing_snapshot=self.pricing_snapshot,
            context_assembler=self.context_assembler,
            invoke_fn=self.invoke_fn,
        )

    async def invoke(
        self,
        *,
        messages: list,
        phase: str,
        call_index: int,
        public_output: bool | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        invoke = self.invoke_fn or invoke_llm
        kwargs = {
            "model": self.model,
            "messages": messages,
            "phase": phase,
            "call_index": call_index,
            "provider": self.provider,
            "model_name": self.model_name,
            "pricing_snapshot": self.pricing_snapshot,
            "context_assembler": self.context_assembler,
        }
        if public_output is not None:
            kwargs["public_output"] = public_output
        return await invoke(**kwargs)
