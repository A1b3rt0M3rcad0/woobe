from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from modules.agent.application.interfaces.knowledge import KnowledgeStrategy
from modules.agent.application.rag.knowledge_strategy import RAGKnowledgeStrategy


DEFAULT_KNOWLEDGE_STRATEGY = "rag"
KnowledgeStrategyFactory = Callable[[], KnowledgeStrategy]


@dataclass(frozen=True, slots=True)
class KnowledgeStrategyDescriptor:
    """Backend-owned product metadata for one selectable Knowledge algorithm."""

    name: str
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    is_default: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "is_default": self.is_default,
        }


class KnowledgeStrategyRegistryError(ValueError):
    pass


class DuplicateKnowledgeStrategyError(KnowledgeStrategyRegistryError):
    pass


class UnknownKnowledgeStrategyError(KnowledgeStrategyRegistryError):
    pass


class KnowledgeStrategyRegistry:
    """Explicit in-process catalog for programmable Knowledge algorithms."""

    def __init__(self) -> None:
        self._entries: dict[
            str,
            tuple[KnowledgeStrategyFactory, KnowledgeStrategyDescriptor],
        ] = {}

    def register(
        self,
        descriptor: KnowledgeStrategyDescriptor,
        factory: KnowledgeStrategyFactory,
    ) -> None:
        name = descriptor.name.strip().lower()
        if not name:
            raise ValueError("Knowledge Strategy name must not be empty")
        if name in self._entries:
            raise DuplicateKnowledgeStrategyError(
                f"Knowledge Strategy already registered: {name}"
            )
        self._entries[name] = (factory, descriptor)

    def contains(self, name: str) -> bool:
        return name.strip().lower() in self._entries

    def resolve(self, name: str) -> KnowledgeStrategy:
        key = name.strip().lower()
        entry = self._entries.get(key)
        if entry is None:
            raise UnknownKnowledgeStrategyError(
                f"Unknown Knowledge Strategy: {key or name}"
            )
        strategy = entry[0]()
        if not isinstance(strategy, KnowledgeStrategy):
            raise TypeError(
                f"Knowledge Strategy factory for {key} returned an incompatible object"
            )
        return strategy

    def list_descriptors(self) -> tuple[KnowledgeStrategyDescriptor, ...]:
        return tuple(
            descriptor
            for _name, (_factory, descriptor) in sorted(
                self._entries.items(),
                key=lambda item: (
                    0 if item[1][1].is_default else 1,
                    item[1][1].display_name.lower(),
                    item[0],
                ),
            )
        )


_RAG_DESCRIPTOR = KnowledgeStrategyDescriptor(
    name="rag",
    display_name="RAG",
    description=(
        "Conversation-aware Knowledge retrieval backed by the configured RAG runtime."
    ),
    behavior=(
        "Builds the retrieval query from the read-only conversation, then delegates "
        "the query to the frozen RAG binding selected for the Run."
    ),
    recommended_for=(
        "Agents grounded in versioned document Knowledge.",
        "Retrieval flows using immutable vector snapshots and selectable RAG algorithms.",
    ),
    capabilities=(
        "Current-message and conversation-context query construction.",
        "Configurable history window without leaking query policy into Execution.",
        "Delegation to the configured RAG Strategy and frozen retrieval binding.",
    ),
    limitations=(
        "Requires a prepared RAG binding to return Knowledge.",
        "The built-in implementation currently constructs textual retrieval queries.",
    ),
    is_default=True,
)


def build_knowledge_strategy_registry() -> KnowledgeStrategyRegistry:
    registry = KnowledgeStrategyRegistry()
    registry.register(_RAG_DESCRIPTOR, RAGKnowledgeStrategy)
    return registry


SUPPORTED_KNOWLEDGE_STRATEGIES = frozenset(
    descriptor.name
    for descriptor in build_knowledge_strategy_registry().list_descriptors()
)


def list_knowledge_strategies() -> list[dict[str, object]]:
    return [
        descriptor.as_dict()
        for descriptor in build_knowledge_strategy_registry().list_descriptors()
    ]


__all__ = [
    "DEFAULT_KNOWLEDGE_STRATEGY",
    "DuplicateKnowledgeStrategyError",
    "KnowledgeStrategyDescriptor",
    "KnowledgeStrategyRegistry",
    "KnowledgeStrategyRegistryError",
    "SUPPORTED_KNOWLEDGE_STRATEGIES",
    "UnknownKnowledgeStrategyError",
    "build_knowledge_strategy_registry",
    "list_knowledge_strategies",
]
