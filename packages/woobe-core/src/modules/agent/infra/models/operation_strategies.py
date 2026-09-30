from __future__ import annotations

from modules.agent.application.interfaces.model_runtime import (
    ModelOperationStrategy,
    ModelOperationStrategyRegistry,
    ModelRequest,
    ModelResult,
    ModelRuntime,
)
from modules.agent.domain.model_spec import ModelOperations


class LanguageGenerationModelStrategy:
    key = ModelOperations.LANGUAGE_GENERATE

    def supports(self, spec) -> bool:
        return spec.supports_operation(self.key)

    async def invoke(
        self,
        runtime: ModelRuntime,
        request: ModelRequest,
    ) -> ModelResult:
        if request.operation != self.key:
            raise ValueError(
                f"Language generation strategy cannot execute {request.operation}"
            )
        if not self.supports(runtime.spec):
            raise ValueError(
                f"Model {runtime.spec.model_id} does not support {self.key}"
            )
        return await runtime.invoke(request)


class EmbeddingModelStrategy:
    key = ModelOperations.EMBEDDING_CREATE

    def supports(self, spec) -> bool:
        return spec.supports_operation(self.key)

    async def invoke(
        self,
        runtime: ModelRuntime,
        request: ModelRequest,
    ) -> ModelResult:
        if request.operation != self.key:
            raise ValueError(
                f"Embedding strategy cannot execute {request.operation}"
            )
        if not self.supports(runtime.spec):
            raise ValueError(
                f"Model {runtime.spec.model_id} does not support {self.key}"
            )
        return await runtime.invoke(request)


def build_model_operation_strategy_registry() -> ModelOperationStrategyRegistry:
    registry = ModelOperationStrategyRegistry()
    registry.register(LanguageGenerationModelStrategy())
    registry.register(EmbeddingModelStrategy())
    return registry


__all__ = [
    "EmbeddingModelStrategy",
    "LanguageGenerationModelStrategy",
    "build_model_operation_strategy_registry",
]
