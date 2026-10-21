from __future__ import annotations

import pytest

from modules.agent.application.interfaces.knowledge import (
    KnowledgeRequest,
    KnowledgeStrategy,
)
from modules.agent.application.rag.no_knowledge_strategy import NoKnowledgeStrategy
from modules.agent.infra.execution.runtime_preparation import prepare_rag_binding
from modules.agent.application.knowledge_strategy_config import (
    canonicalize_knowledge_strategy_runtime_config,
    knowledge_strategy_from_runtime_config,
)
from modules.agent.application.knowledge_strategy_registry import (
    DEFAULT_KNOWLEDGE_STRATEGY,
    build_knowledge_strategy_registry,
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
    assert knowledge_strategy_from_runtime_config({"knowledge_strategy": " NONE "}) == "none"

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

    assert [item["name"] for item in catalog] == ["rag", "none"]
    assert catalog[0]["is_default"] is True
    assert catalog[0]["capabilities"]
    assert catalog[0]["limitations"]
    assert catalog[1]["is_default"] is False


@pytest.mark.asyncio
async def test_explicit_no_knowledge_strategy_never_calls_available_rag_capability():
    class Capabilities:
        available = True

        async def retrieve(self, *, query):
            raise AssertionError(f"Unexpected RAG call: {query}")

    strategy = build_knowledge_strategy_registry().resolve("none")
    assert isinstance(strategy, NoKnowledgeStrategy)
    result = await strategy.retrieve(
        KnowledgeRequest(conversation=object(), runtime_config={"rag": {}}),
        Capabilities(),
    )
    assert result.content is None
    assert result.found is False
    assert result.metadata == {"knowledge_strategy": "none"}


@pytest.mark.asyncio
async def test_no_knowledge_skips_even_a_stale_vector_binding_before_repository_access():
    agent = type("Agent", (), {"settings": {
        "runtime_config": {"knowledge_strategy": "none"},
        "knowledge_version_id": "stale-version",
    }})()
    assert await prepare_rag_binding(object(), agent=agent) is None


def test_no_knowledge_does_not_enable_knowledge_requirements_in_model_runtime_plan():
    from types import SimpleNamespace

    from modules.agent.application.rag.knowledge_strategy import RAGKnowledgeStrategy
    from modules.agent.infra.execution.strategy_runtime.builder import (
        _configured_knowledge_strategy,
    )

    assert _configured_knowledge_strategy(SimpleNamespace(
        knowledge_strategy=NoKnowledgeStrategy(),
        knowledge_retrieve=lambda **_: None,
    )) is None
    assert _configured_knowledge_strategy(SimpleNamespace(
        knowledge_strategy=RAGKnowledgeStrategy(),
        knowledge_retrieve=lambda **_: None,
    )) == "rag"
