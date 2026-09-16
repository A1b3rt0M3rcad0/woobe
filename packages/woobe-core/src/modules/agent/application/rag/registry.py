from __future__ import annotations

from modules.agent.application.interfaces.rag import RAGStrategy


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

    def register(self, name: str, strategy: RAGStrategy) -> None:
        key = _strategy_name(name)
        if not key:
            raise ValueError("RAG strategy name cannot be empty")
        if key in self._strategies:
            raise DuplicateRAGStrategyError(f"RAG strategy is already registered: {key}")
        self._strategies[key] = strategy

    def resolve(self, name: str) -> RAGStrategy:
        key = _strategy_name(name)
        try:
            return self._strategies[key]
        except KeyError as exc:
            raise UnknownRAGStrategyError(f"Unknown RAG strategy: {key or name}") from exc

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._strategies))
