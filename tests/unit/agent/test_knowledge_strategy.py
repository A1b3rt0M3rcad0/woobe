from __future__ import annotations

import pytest

from modules.agent.application.interfaces.knowledge import KnowledgeStrategy
from modules.agent.application.knowledge_strategy_registry import (
    DEFAULT_KNOWLEDGE_STRATEGY,
    build_knowledge_strategy_registry,
    canonicalize_knowledge_strategy_runtime_config,
    knowledge_strategy_from_runtime_config,
    list_knowledge_strategies,
)
from shared.contracts.errors import ValidationError


def test_missing_knowledge_strategy_is_permanently_rag() -> None:
    assert knowledge_strategy_from_runtime_config(None) == "rag"
    assert knowledge_strategy_from_runtime_config({}) == "rag"
    assert DEFAULT_KNOWLEDGE_STRATEGY == "rag"


def test_explicit_knowledge_strategy_is_normalized_and_validated() -> None:
    assert (
        knowledge_strategy_from_runtime_config(
            {"knowledge_strategy": "  RAG  "}
        )
        == "rag"
    )

    with pytest.raises(ValidationError, match="Unsupported knowledge strategy"):
        knowledge_strategy_from_runtime_config(
            {"knowledge_strategy": "pageindex"}
        )


def test_knowledge_strategy_canonicalization_preserves_other_runtime_config() -> None:
    source = {
        "execution_strategy": "standard",
        "rag": {"strategy": "classic", "top_k": 5},
    }

    result = canonicalize_knowledge_strategy_runtime_config(source)

    assert result is not source
    assert result["knowledge_strategy"] == "rag"
    assert result["execution_strategy"] == "standard"
    assert result["rag"] == {"strategy": "classic", "top_k": 5}


def test_knowledge_strategy_registry_resolves_runtime_implementation() -> None:
    registry = build_knowledge_strategy_registry()
    strategy = registry.resolve("rag")

    assert isinstance(strategy, KnowledgeStrategy)
    assert strategy.name == "rag"
    assert registry.contains("rag")


def test_knowledge_strategy_catalog_describes_default_algorithm() -> None:
    catalog = list_knowledge_strategies()

    assert len(catalog) == 1
    assert catalog[0]["name"] == "rag"
    assert catalog[0]["is_default"] is True
    assert catalog[0]["capabilities"]
    assert catalog[0]["limitations"]
