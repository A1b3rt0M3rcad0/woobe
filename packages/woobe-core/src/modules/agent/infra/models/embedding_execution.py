from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.interfaces.model_compatibility import (
    CompatibilityMode,
    ExecutionStrategySpec,
)
from modules.agent.application.interfaces.model_output import (
    EmbeddingModelOutputStrategy,
)
from modules.agent.application.interfaces.model_runtime import (
    ModelInput,
    ModelOperationStrategy,
    ModelRequest,
    ModelResult,
    ModelRuntime,
)
from modules.agent.application.interfaces.model_runtime_plan import (
    ModelRuntimePlan,
    ModelRuntimePlanBuilder,
)
from modules.agent.domain.model_spec import (
    ModelModalities,
    ModelOperations,
)


EMBEDDING_EXECUTION_SPEC = ExecutionStrategySpec(
    name="embedding",
    operations=frozenset({ModelOperations.EMBEDDING_CREATE}),
    requires_conversation=False,
    allowed_input_modalities=frozenset({ModelModalities.TEXT}),
    allowed_output_modalities=frozenset({ModelModalities.EMBEDDING}),
    context_mode=CompatibilityMode.UNSUPPORTED,
    knowledge_mode=CompatibilityMode.UNSUPPORTED,
    tools_mode=CompatibilityMode.UNSUPPORTED,
)


@dataclass(frozen=True, slots=True)
class EmbeddingExecutionRequest:
    texts: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.texts:
            raise ValueError("Embedding execution requires at least one text")
        if any(not isinstance(text, str) or not text for text in self.texts):
            raise ValueError("Embedding execution texts must be non-empty strings")


@dataclass(frozen=True, slots=True)
class EmbeddingExecutionResult:
    result: ModelResult
    runtime_plan: ModelRuntimePlan


class EmbeddingExecutionStrategy:
    """Non-conversational embedding execution.

    It intentionally receives no Conversation, Context Manager, Knowledge or Tools.
    """

    name = "embedding"
    spec = EMBEDDING_EXECUTION_SPEC

    def __init__(
        self,
        *,
        operation_strategy: ModelOperationStrategy,
        output_strategy: EmbeddingModelOutputStrategy | None = None,
    ) -> None:
        self._operation_strategy = operation_strategy
        self._output_strategy = output_strategy or EmbeddingModelOutputStrategy()

    async def execute(
        self,
        *,
        runtime: ModelRuntime,
        request: EmbeddingExecutionRequest,
    ) -> EmbeddingExecutionResult:
        plan = ModelRuntimePlanBuilder().build(
            model=runtime.spec,
            execution=self.spec,
            model_strategy=ModelOperations.EMBEDDING_CREATE,
            context_strategy=None,
            knowledge_strategy=None,
            output_strategy=self._output_strategy.key,
            tools_enabled=False,
            required_input_modalities=frozenset({ModelModalities.TEXT}),
            required_output_modalities=frozenset({ModelModalities.EMBEDDING}),
        )
        model_request = ModelRequest(
            operation=ModelOperations.EMBEDDING_CREATE,
            inputs=tuple(
                ModelInput(modality=ModelModalities.TEXT, value=text)
                for text in request.texts
            ),
        )
        result = await self._operation_strategy.invoke(runtime, model_request)
        self._output_strategy.validate(result)
        return EmbeddingExecutionResult(
            result=result,
            runtime_plan=plan,
        )


__all__ = [
    "EMBEDDING_EXECUTION_SPEC",
    "EmbeddingExecutionRequest",
    "EmbeddingExecutionResult",
    "EmbeddingExecutionStrategy",
]
