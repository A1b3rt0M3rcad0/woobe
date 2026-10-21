from __future__ import annotations

from modules.agent.application.interfaces.model_runtime import (
    ModelOperationStrategyRegistry,
    ModelRequest,
    ModelResult,
    ModelRuntime,
)
from modules.agent.domain.model_spec import ModelModalities, ModelOperations


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


class ImageGenerationModelStrategy:
    key = ModelOperations.IMAGE_GENERATE

    def supports(self, spec) -> bool:
        return (
            spec.supports_operation(self.key)
            and spec.produces(ModelModalities.IMAGE)
        )

    async def invoke(self, runtime: ModelRuntime, request: ModelRequest) -> ModelResult:
        if request.operation != self.key:
            raise ValueError("Image generation strategy cannot execute another operation")
        if not self.supports(runtime.spec):
            raise ValueError("Model does not support image.generate")
        if request.tools:
            raise ValueError("Image generation does not bind chat Tools")
        return await runtime.invoke(request)


def build_model_operation_strategy_registry() -> ModelOperationStrategyRegistry:
    registry = ModelOperationStrategyRegistry()
    registry.register(LanguageGenerationModelStrategy())
    registry.register(EmbeddingModelStrategy())
    registry.register(ImageGenerationModelStrategy())
    return registry


__all__ = [
    "EmbeddingModelStrategy",
    "ImageGenerationModelStrategy",
    "LanguageGenerationModelStrategy",
    "build_model_operation_strategy_registry",
]
