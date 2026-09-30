from __future__ import annotations

from typing import Protocol, runtime_checkable

from modules.agent.application.interfaces.model_runtime import ModelResult


@runtime_checkable
class ModelOutputStrategy(Protocol):
    key: str

    def validate(self, result: ModelResult) -> None: ...


class TextModelOutputStrategy:
    key = "text"

    def validate(self, result: ModelResult) -> None:
        outputs = result.outputs_for("text")
        if not outputs:
            raise ValueError("Model result does not contain text output")
        if not any(
            isinstance(output.value, str) and output.value.strip()
            for output in outputs
        ):
            raise ValueError("Model result contains only empty text output")


class EmbeddingModelOutputStrategy:
    key = "embedding"

    def validate(self, result: ModelResult) -> None:
        outputs = result.outputs_for("embedding")
        if not outputs:
            raise ValueError("Model result does not contain embedding output")
        for output in outputs:
            vector = output.value
            if not isinstance(vector, (list, tuple)) or not vector:
                raise ValueError("Embedding output must be a non-empty vector")
            if any(
                not isinstance(value, (int, float)) or isinstance(value, bool)
                for value in vector
            ):
                raise ValueError("Embedding vector values must be numeric")


class ModelOutputStrategyRegistry:
    __slots__ = ("_strategies",)

    def __init__(self) -> None:
        self._strategies: dict[str, ModelOutputStrategy] = {}

    def register(self, strategy: ModelOutputStrategy) -> None:
        key = str(strategy.key).strip()
        if not key:
            raise ValueError("Model output strategy key must not be empty")
        if key in self._strategies:
            raise ValueError(f"Model output strategy already registered: {key}")
        self._strategies[key] = strategy

    def resolve(self, key: str) -> ModelOutputStrategy:
        strategy = self._strategies.get(str(key).strip())
        if strategy is None:
            raise ValueError(f"Unknown Model output strategy: {key}")
        return strategy


def build_model_output_strategy_registry() -> ModelOutputStrategyRegistry:
    registry = ModelOutputStrategyRegistry()
    registry.register(TextModelOutputStrategy())
    registry.register(EmbeddingModelOutputStrategy())
    return registry


__all__ = [
    "EmbeddingModelOutputStrategy",
    "ModelOutputStrategy",
    "ModelOutputStrategyRegistry",
    "TextModelOutputStrategy",
    "build_model_output_strategy_registry",
]
