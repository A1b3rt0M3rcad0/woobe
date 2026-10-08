from __future__ import annotations

from dataclasses import dataclass, field
from copy import deepcopy
from modules.agent.application.interfaces.rag import RAGStrategy
from modules.agent.application.strategy_configuration import (
    check_strategy_config_schema,
    empty_strategy_config_schema,
    validate_strategy_configuration,
)


@dataclass(frozen=True)
class RAGStrategyDescriptor:
    name: str
    config_schema: dict = field(default_factory=empty_strategy_config_schema)
    config_schema_version: str = "1"

    def __post_init__(self):
        check_strategy_config_schema(self.config_schema, self.config_schema_version)
        object.__setattr__(self, "config_schema", deepcopy(self.config_schema))

    def as_dict(self):
        return {
            "name": self.name,
            "config_schema": deepcopy(self.config_schema),
            "config_schema_version": self.config_schema_version,
        }


class UnknownRAGStrategyError(LookupError):
    pass


class DuplicateRAGStrategyError(ValueError):
    pass


def _strategy_name(value: str) -> str:
    return value.strip().lower()


class RAGStrategyRegistry:
    """Explicit registry for supported RAG algorithms."""

    def __init__(self) -> None:
        self._strategies: dict[str, RAGStrategy] = {}
        self._descriptors: dict[str, RAGStrategyDescriptor] = {}

    def register(
        self,
        name: str,
        strategy: RAGStrategy,
        *,
        config_schema=None,
        config_schema_version="1",
    ) -> None:
        key = _strategy_name(name)
        if not key:
            raise ValueError("RAG strategy name cannot be empty")
        if key in self._strategies:
            raise DuplicateRAGStrategyError(
                f"RAG strategy is already registered: {key}"
            )
        descriptor = RAGStrategyDescriptor(
            key,
            empty_strategy_config_schema() if config_schema is None else config_schema,
            config_schema_version,
        )
        self._strategies[key] = strategy
        self._descriptors[key] = descriptor

    def resolve(self, name: str) -> RAGStrategy:
        key = _strategy_name(name)
        try:
            return self._strategies[key]
        except KeyError as exc:
            raise UnknownRAGStrategyError(
                f"Unknown RAG strategy: {key or name}"
            ) from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._strategies))

    def describe(self, name: str) -> RAGStrategyDescriptor:
        self.resolve(name)
        return self._descriptors[_strategy_name(name)]

    def validate_configuration(self, name, value, *, schema_version):
        return validate_strategy_configuration(
            self.describe(name), value, schema_version=schema_version
        )


def build_rag_strategy_registry() -> RAGStrategyRegistry:
    from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy

    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    return registry
