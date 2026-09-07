from __future__ import annotations

from modules.agent.application.interfaces.knowledge_strategy import (
    STANDARD_RAG_STRATEGY_KEY,
    KnowledgeStrategyKey,
    knowledge_strategy_selection_from_runtime_config,
)
from modules.agent.application.knowledge_strategy_registry import (
    build_knowledge_strategy_registry,
    canonicalize_knowledge_strategy_runtime_config,
    list_knowledge_strategies,
)


def test_historical_runtime_config_resolves_to_standard_rag_v1() -> None:
    selection = knowledge_strategy_selection_from_runtime_config({"rag": {"top_k": 5}})

    assert selection.selection_key == KnowledgeStrategyKey("default", "v1")
    assert selection.strategy_key == STANDARD_RAG_STRATEGY_KEY


def test_canonicalization_freezes_selection_and_strategy_identity() -> None:
    runtime = canonicalize_knowledge_strategy_runtime_config(
        {"rag": {"top_k": 5}},
        use_current_default_if_missing=True,
    )

    assert runtime["knowledge_strategy"] == {
        "name": "default",
        "version": "v1",
        "strategy_name": "std-rag",
        "strategy_version": "v1",
    }
    assert runtime["rag"] == {"top_k": 5}


def test_explicit_strategy_identity_is_snapshot_safe() -> None:
    runtime = canonicalize_knowledge_strategy_runtime_config(
        {
            "knowledge_strategy": {
                "name": "std-rag",
                "version": "v1",
            }
        }
    )

    assert runtime["knowledge_strategy"]["strategy_name"] == "std-rag"
    assert runtime["knowledge_strategy"]["strategy_version"] == "v1"


def test_registry_exposes_default_alias_and_concrete_strategy() -> None:
    descriptors = list_knowledge_strategies()

    assert descriptors[0]["name"] == "default"
    assert descriptors[0]["strategy_name"] == "std-rag"
    assert descriptors[0]["is_default"] is True
    assert any(
        item["name"] == "std-rag" and item["version"] == "v1"
        for item in descriptors
    )


def test_registry_builds_standard_strategy() -> None:
    registry = build_knowledge_strategy_registry()

    strategy = registry.create_strategy(STANDARD_RAG_STRATEGY_KEY)

    assert type(strategy).__name__ == "StandardVectorRAGStrategy"
