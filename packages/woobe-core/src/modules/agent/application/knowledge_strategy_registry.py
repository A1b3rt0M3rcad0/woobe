from __future__ import annotations

from collections.abc import Callable
from copy import deepcopy
from dataclasses import dataclass, replace

from modules.agent.application.interfaces.knowledge_strategy import (
    LEGACY_DEFAULT_KNOWLEDGE_STRATEGY_KEY,
    STANDARD_RAG_STRATEGY_KEY,
    KnowledgePreparationRequest,
    KnowledgePreparedBinding,
    KnowledgeRetrievalOutput,
    KnowledgeRetrievalRequest,
    KnowledgeRuntimeStrategy,
    KnowledgeStrategyKey,
    KnowledgeStrategySelection,
    knowledge_strategy_selection_from_runtime_config,
)
from modules.agent.application.knowledge_strategies.standard_rag import (
    StandardVectorRAGStrategy,
)
from shared.contracts.errors import ValidationError


DEFAULT_KNOWLEDGE_STRATEGY_SETTING = "std-rag:v1"
KnowledgeStrategyFactory = Callable[[], KnowledgeRuntimeStrategy]


@dataclass(frozen=True, slots=True)
class KnowledgeStrategyDescriptor:
    key: KnowledgeStrategyKey
    strategy_key: KnowledgeStrategyKey
    display_name: str
    description: str
    behavior: str
    recommended_for: tuple[str, ...]
    capabilities: tuple[str, ...]
    limitations: tuple[str, ...]
    configuration: str
    is_default: bool = False
    is_system_default_alias: bool = False

    def as_dict(self) -> dict[str, object]:
        return {
            "name": self.key.name,
            "version": self.key.version,
            "strategy_name": self.strategy_key.name,
            "strategy_version": self.strategy_key.version,
            "display_name": self.display_name,
            "description": self.description,
            "behavior": self.behavior,
            "recommended_for": list(self.recommended_for),
            "capabilities": list(self.capabilities),
            "limitations": list(self.limitations),
            "configuration": self.configuration,
            "is_default": self.is_default,
            "is_system_default_alias": self.is_system_default_alias,
        }


class KnowledgeStrategyRegistryError(ValueError):
    pass


class DuplicateKnowledgeStrategyError(KnowledgeStrategyRegistryError):
    pass


class UnknownKnowledgeStrategyError(KnowledgeStrategyRegistryError):
    pass


class InvalidDefaultKnowledgeStrategyError(KnowledgeStrategyRegistryError):
    pass


class KnowledgeStrategyRegistry:
    __slots__ = ("_entries", "_current_default_key")

    def __init__(self) -> None:
        self._entries: dict[
            KnowledgeStrategyKey,
            tuple[KnowledgeStrategyFactory, KnowledgeStrategyDescriptor],
        ] = {}
        self._current_default_key: KnowledgeStrategyKey | None = None

    def register(
        self,
        key: KnowledgeStrategyKey,
        factory: KnowledgeStrategyFactory,
        *,
        descriptor: KnowledgeStrategyDescriptor,
    ) -> None:
        if key.name == "default":
            raise ValueError(
                "The 'default' Knowledge strategy identity is reserved for the system-default alias"
            )
        if key in self._entries:
            raise DuplicateKnowledgeStrategyError(
                f"Knowledge strategy already registered: {key}"
            )
        if descriptor.key != key or descriptor.strategy_key != key:
            raise ValueError(
                "Explicit Knowledge strategy descriptor identities must match registration key"
            )
        self._entries[key] = (factory, descriptor)

    def register_default_alias(self, *, strategy_key: KnowledgeStrategyKey) -> None:
        target = self._entries.get(strategy_key)
        if target is None:
            raise InvalidDefaultKnowledgeStrategyError(
                f"Configured default Knowledge strategy is not registered: {strategy_key}"
            )
        if self._current_default_key is not None:
            raise InvalidDefaultKnowledgeStrategyError(
                "System default Knowledge strategy is already registered"
            )
        alias_key = KnowledgeStrategyKey(name="default", version=strategy_key.version)
        factory, descriptor = target
        self._entries[alias_key] = (
            factory,
            replace(
                descriptor,
                key=alias_key,
                strategy_key=strategy_key,
                is_default=True,
                is_system_default_alias=True,
            ),
        )
        self._current_default_key = alias_key

    def contains(self, key: KnowledgeStrategyKey) -> bool:
        return key in self._entries

    def contains_strategy(self, key: KnowledgeStrategyKey) -> bool:
        item = self._entries.get(key)
        return bool(item and not item[1].is_system_default_alias)

    def create_strategy(self, key: KnowledgeStrategyKey) -> KnowledgeRuntimeStrategy:
        item = self._entries.get(key)
        if item is None or item[1].is_system_default_alias:
            raise UnknownKnowledgeStrategyError(f"Unknown Knowledge strategy: {key}")
        strategy = item[0]()
        if not isinstance(strategy, KnowledgeRuntimeStrategy):
            raise TypeError(f"Knowledge strategy factory returned an invalid object: {key}")
        return strategy

    def current_default(self) -> KnowledgeStrategyDescriptor:
        if self._current_default_key is None:
            raise InvalidDefaultKnowledgeStrategyError(
                "Knowledge strategy registry has no system default"
            )
        return self._entries[self._current_default_key][1]

    def list_descriptors(self) -> tuple[KnowledgeStrategyDescriptor, ...]:
        return tuple(
            self._entries[key][1]
            for key in sorted(
                self._entries,
                key=lambda item: (
                    0 if self._entries[item][1].is_default else 1,
                    item.name,
                    item.version,
                ),
            )
        )


_STANDARD_DESCRIPTOR = KnowledgeStrategyDescriptor(
    key=STANDARD_RAG_STRATEGY_KEY,
    strategy_key=STANDARD_RAG_STRATEGY_KEY,
    display_name="Standard RAG",
    description="Immutable Vector Snapshot retrieval using embedding similarity.",
    behavior=(
        "Builds a conversation-aware retrieval query, embeds it, searches the frozen "
        "Vector Snapshot, applies score/document limits, and materializes selected chunks."
    ),
    recommended_for=(
        "General-purpose document grounded Agents.",
        "Production workloads requiring immutable Knowledge replay and rollback.",
    ),
    capabilities=(
        "Immutable Vector Snapshot binding.",
        "Conversation-aware or current-message retrieval queries.",
        "Similarity filtering, per-document limits, Top K and grounding policy.",
        "Exact Knowledge and vector artifact provenance.",
    ),
    limitations=(
        "Uses dense vector similarity only.",
        "Does not perform lexical fusion, reranking, graph traversal or iterative planning.",
    ),
    configuration="RAGRuntimeConfig v1",
)


def _configured_default_strategy(value: str) -> KnowledgeStrategyKey:
    try:
        key = KnowledgeStrategyKey.parse(value)
    except ValueError as exc:
        raise InvalidDefaultKnowledgeStrategyError(
            "WOOBE_DEFAULT_KNOWLEDGE_STRATEGY must use '<strategy>:<version>'"
        ) from exc
    if key.name == "default":
        raise InvalidDefaultKnowledgeStrategyError(
            "WOOBE_DEFAULT_KNOWLEDGE_STRATEGY must identify a concrete strategy"
        )
    return key


def build_knowledge_strategy_registry(
    default_knowledge_strategy: str = DEFAULT_KNOWLEDGE_STRATEGY_SETTING,
) -> KnowledgeStrategyRegistry:
    registry = KnowledgeStrategyRegistry()
    registry.register(
        STANDARD_RAG_STRATEGY_KEY,
        StandardVectorRAGStrategy,
        descriptor=_STANDARD_DESCRIPTOR,
    )
    registry.register_default_alias(
        strategy_key=_configured_default_strategy(default_knowledge_strategy)
    )
    return registry


class RegistryKnowledgeRuntimeStrategy:
    __slots__ = ("_registry",)

    def __init__(self, registry: KnowledgeStrategyRegistry) -> None:
        self._registry = registry

    async def prepare(
        self,
        request: KnowledgePreparationRequest,
    ) -> KnowledgePreparedBinding | None:
        settings = getattr(request.agent, "settings", None)
        runtime_config = (
            settings.get("runtime_config")
            if isinstance(settings, dict)
            else None
        )
        selection = knowledge_strategy_selection_from_runtime_config(runtime_config)
        return await self._registry.create_strategy(selection.strategy_key).prepare(request)

    async def retrieve(
        self,
        request: KnowledgeRetrievalRequest,
    ) -> KnowledgeRetrievalOutput:
        return await self._registry.create_strategy(
            request.binding.strategy_key
        ).retrieve(request)


def build_runtime_knowledge_strategy(
    default_knowledge_strategy: str = DEFAULT_KNOWLEDGE_STRATEGY_SETTING,
) -> KnowledgeRuntimeStrategy:
    return RegistryKnowledgeRuntimeStrategy(
        build_knowledge_strategy_registry(default_knowledge_strategy)
    )


def _has_selection(value: object) -> bool:
    return isinstance(value, dict) and isinstance(value.get("knowledge_strategy"), dict)


def validate_knowledge_strategy_runtime_config(
    value: object,
    *,
    default_knowledge_strategy: str = DEFAULT_KNOWLEDGE_STRATEGY_SETTING,
    use_current_default_if_missing: bool = False,
) -> KnowledgeStrategySelection:
    registry = build_knowledge_strategy_registry(default_knowledge_strategy)
    if use_current_default_if_missing and not _has_selection(value):
        descriptor = registry.current_default()
        return KnowledgeStrategySelection(
            selection_key=descriptor.key,
            strategy_key=descriptor.strategy_key,
        )
    try:
        selection = knowledge_strategy_selection_from_runtime_config(value)
    except ValueError as exc:
        raise ValidationError(str(exc)) from exc
    if not registry.contains_strategy(selection.strategy_key):
        raise ValidationError(
            f"Unsupported Knowledge strategy: {selection.strategy_key}"
        )
    if selection.selection_key.name == "default":
        if selection.selection_key.version != selection.strategy_key.version:
            raise ValidationError(
                "System default Knowledge strategy version must match frozen strategy version"
            )
    elif selection.selection_key != selection.strategy_key:
        raise ValidationError(
            "Explicit Knowledge strategy selection must match resolved strategy"
        )
    return selection


def canonicalize_knowledge_strategy_runtime_config(
    value: object,
    *,
    default_knowledge_strategy: str = DEFAULT_KNOWLEDGE_STRATEGY_SETTING,
    use_current_default_if_missing: bool = False,
) -> dict:
    if value is not None and not isinstance(value, dict):
        raise ValidationError("Agent runtime_config must be an object")
    runtime_config = deepcopy(value) if isinstance(value, dict) else {}
    selection = validate_knowledge_strategy_runtime_config(
        runtime_config,
        default_knowledge_strategy=default_knowledge_strategy,
        use_current_default_if_missing=use_current_default_if_missing,
    )
    runtime_config["knowledge_strategy"] = selection.as_dict()
    return runtime_config


def list_knowledge_strategies(
    default_knowledge_strategy: str = DEFAULT_KNOWLEDGE_STRATEGY_SETTING,
) -> list[dict[str, object]]:
    return [
        descriptor.as_dict()
        for descriptor in build_knowledge_strategy_registry(
            default_knowledge_strategy
        ).list_descriptors()
    ]
