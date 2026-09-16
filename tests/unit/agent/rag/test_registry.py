from __future__ import annotations

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.rag.registry import (
    DuplicateRAGStrategyError,
    RAGStrategyRegistry,
    UnknownRAGStrategyError,
)


class _Strategy:
    async def retrieve(self, request, capabilities):
        raise NotImplementedError


def test_rag_runtime_config_defaults_to_classic_for_existing_agents() -> None:
    config = RAGRuntimeConfig.model_validate({})

    assert config.strategy == "classic"
    assert config.model_dump()["strategy"] == "classic"


def test_rag_runtime_config_normalizes_explicit_strategy_name() -> None:
    config = RAGRuntimeConfig.model_validate({"strategy": "  CLASSIC  "})

    assert config.strategy == "classic"


def test_registry_resolves_registered_strategy_without_implicit_fallback() -> None:
    registry = RAGStrategyRegistry()
    strategy = _Strategy()
    registry.register("classic", strategy)

    assert registry.resolve(" CLASSIC ") is strategy
    assert registry.names() == ("classic",)

    with pytest.raises(UnknownRAGStrategyError, match="Unknown RAG strategy: agentic"):
        registry.resolve("agentic")


def test_registry_rejects_duplicate_strategy_names() -> None:
    registry = RAGStrategyRegistry()
    registry.register("classic", _Strategy())

    with pytest.raises(DuplicateRAGStrategyError, match="already registered"):
        registry.register("CLASSIC", _Strategy())
