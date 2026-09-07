from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class KnowledgeStrategyKey:
    """Stable, serializable identity for one Knowledge runtime strategy."""

    name: str
    version: str

    def __post_init__(self) -> None:
        name = self.name.strip()
        version = self.version.strip()
        if not name:
            raise ValueError("Knowledge strategy name must not be empty")
        if not version:
            raise ValueError("Knowledge strategy version must not be empty")
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)

    @classmethod
    def parse(cls, value: str) -> KnowledgeStrategyKey:
        normalized = value.strip()
        name, separator, version = normalized.partition(":")
        if not separator or not name.strip() or not version.strip() or ":" in version:
            raise ValueError("Knowledge strategy key must use '<name>:<version>'")
        return cls(name=name, version=version)

    def __str__(self) -> str:
        return f"{self.name}:{self.version}"

    def as_dict(self) -> dict[str, str]:
        return {"name": self.name, "version": self.version}


LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY = KnowledgeStrategyKey(
    name="default",
    version="v1",
)
STANDARD_RAG_STRATEGY_KEY = KnowledgeStrategyKey(name="std-rag", version="v1")
DEFAULT_KNOWLEDGE_STRATEGY_KEY = LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY


@dataclass(frozen=True, slots=True)
class KnowledgeStrategySelection:
    """Snapshot-safe selection identity and the concrete strategy it resolves to."""

    selection_key: KnowledgeStrategyKey
    strategy_key: KnowledgeStrategyKey

    def as_dict(self) -> dict[str, str]:
        return {
            "name": self.selection_key.name,
            "version": self.selection_key.version,
            "strategy_name": self.strategy_key.name,
            "strategy_version": self.strategy_key.version,
        }


def knowledge_strategy_selection_from_runtime_config(
    value: object,
) -> KnowledgeStrategySelection:
    """Read a frozen Knowledge strategy selection from Agent runtime config.

    Historical snapshots without explicit strategy identity retain the original
    Woobe Vector RAG behavior through ``std-rag:v1``.
    """

    if value is None:
        return KnowledgeStrategySelection(
            selection_key=LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY,
            strategy_key=STANDARD_RAG_STRATEGY_KEY,
        )
    if not isinstance(value, dict):
        raise ValueError("Agent runtime_config must be an object")

    raw = value.get("knowledge_strategy")
    if raw is None:
        return KnowledgeStrategySelection(
            selection_key=LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY,
            strategy_key=STANDARD_RAG_STRATEGY_KEY,
        )
    if not isinstance(raw, dict):
        raise ValueError("knowledge_strategy must be an object")

    name = raw.get("name")
    version = raw.get("version")
    if not isinstance(name, str) or not isinstance(version, str):
        raise ValueError("knowledge_strategy requires string name and version")
    selection_key = KnowledgeStrategyKey(name=name, version=version)

    strategy_name = raw.get("strategy_name")
    strategy_version = raw.get("strategy_version")
    if strategy_name is None and strategy_version is None:
        strategy_key = (
            STANDARD_RAG_STRATEGY_KEY
            if selection_key == LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY
            else selection_key
        )
    elif isinstance(strategy_name, str) and isinstance(strategy_version, str):
        strategy_key = KnowledgeStrategyKey(
            name=strategy_name,
            version=strategy_version,
        )
    else:
        raise ValueError(
            "knowledge_strategy strategy_name and strategy_version must be provided together"
        )

    if selection_key.name != "default" and strategy_key != selection_key:
        raise ValueError(
            "Explicit Knowledge strategy selections must match their strategy identity"
        )

    return KnowledgeStrategySelection(
        selection_key=selection_key,
        strategy_key=strategy_key,
    )


VectorSearchReader = Callable[..., Awaitable[list[tuple[Any, float]]]]


class KnowledgePreparationResources(Protocol):
    @property
    def knowledge_versions(self) -> Any: ...

    @property
    def vector_snapshots(self) -> Any: ...

    @property
    def provider_models(self) -> Any: ...

    @property
    def provider_credentials(self) -> Any: ...


@dataclass(frozen=True, slots=True)
class KnowledgePreparedBinding:
    """Opaque Run-local state plus the immutable evidence frozen into the Run."""

    strategy_key: KnowledgeStrategyKey
    runtime_state: Any
    snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class KnowledgePreparationRequest:
    agent: Any
    resources: KnowledgePreparationResources


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalRequest:
    agent: Any
    query: str
    history: list[Any]
    binding: KnowledgePreparedBinding
    embedding_factory: Any
    vector_search_reader: VectorSearchReader | None
    encryption_key: str
    runtime_config_source: str


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalOutput:
    context: str | None
    sources: list[Any]
    metadata: dict[str, Any] | None


@runtime_checkable
class KnowledgeRuntimeStrategy(Protocol):
    """Resolve and query Knowledge without exposing strategy details to Runtime."""

    async def prepare(
        self,
        request: KnowledgePreparationRequest,
    ) -> KnowledgePreparedBinding | None: ...

    async def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
    ) -> KnowledgeRetrievalOutput: ...
