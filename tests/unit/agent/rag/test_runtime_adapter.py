from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.embedding_errors import (
    EmbeddingFailure,
    EmbeddingProviderError,
)
from modules.agent.application.interfaces.rag import RAGBinding, RAGResult
from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter
from shared.contracts.errors import ValidationError


class _UnusedEmbeddingFactory:
    def create_embedding_client(self, **_kwargs):
        raise AssertionError("embedding factory should not be used by this test strategy")


class _UnusedVectorSearch:
    async def search(self, **_kwargs):
        raise AssertionError("vector search should not be used by this test strategy")


class _RecordingStrategy:
    def __init__(self, *, result: RAGResult | None = None, error: Exception | None = None) -> None:
        self.result = result or RAGResult(context="context", metrics={"custom_metric": 7})
        self.error = error
        self.calls = []

    async def retrieve(self, request, capabilities):
        self.calls.append((request, capabilities))
        if self.error is not None:
            raise self.error
        return self.result


def _binding(strategy: str = "classic") -> RAGBinding:
    config = RAGRuntimeConfig(
        strategy=strategy,
        top_k=3,
        candidate_k=4,
        max_context_chunks=3,
    )
    knowledge = SimpleNamespace(id=uuid4(), version="kv5")
    snapshot = SimpleNamespace(
        id=uuid4(),
        version="vs8",
        snapshot_hash="hash-8",
        embedding_provider_model_id=uuid4(),
        embedding_provider="openai",
        embedding_model="text-embedding-test",
        embedding_dimensions=3,
    )
    return RAGBinding(
        strategy=strategy,
        config=config,
        knowledge=knowledge,
        snapshot=snapshot,
        provider_model=SimpleNamespace(metadata={}),
        credential=SimpleNamespace(encrypted_secret="ciphertext", metadata={}),
        snapshot_documents=(),
        metadata={
            "strategy": strategy,
            "knowledge_version_id": str(knowledge.id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(snapshot.id),
            "vector_snapshot_version": snapshot.version,
            "snapshot_hash": snapshot.snapshot_hash,
            "embedding_provider_model_id": str(snapshot.embedding_provider_model_id),
            "embedding_provider": snapshot.embedding_provider,
            "embedding_model": snapshot.embedding_model,
            "embedding_dimensions": snapshot.embedding_dimensions,
            "rag_runtime_config": config.model_dump(),
            "rag_runtime_config_source": "production",
            "retrieval_query_mode": config.query_mode,
        },
    )


def _adapter(registry: RAGStrategyRegistry) -> RAGRuntimeAdapter:
    return RAGRuntimeAdapter(
        registry=registry,
        embedding_factory=_UnusedEmbeddingFactory(),
        vector_search=_UnusedVectorSearch(),
        encryption_key="key",
    )


@pytest.mark.asyncio
async def test_runtime_adapter_consumes_frozen_binding_and_merges_metrics() -> None:
    strategy = _RecordingStrategy()
    registry = RAGStrategyRegistry()
    registry.register("classic", strategy)
    binding = _binding()

    result = await _adapter(registry).retrieve(
        binding=binding,
        query="question",
    )

    assert result.context == "context"
    request, _capabilities = strategy.calls[0]
    assert request.config.candidate_k == 4
    assert not hasattr(request.config, "query_mode")
    assert not hasattr(request.config, "history_turns")
    assert request.query == "question"
    assert result.metrics["strategy"] == "classic"
    assert result.metrics["knowledge_version_id"] == str(binding.knowledge.id)
    assert result.metrics["vector_snapshot_id"] == str(binding.snapshot.id)
    assert result.metrics["rag_runtime_config_source"] == "production"
    assert result.metrics["custom_metric"] == 7


@pytest.mark.asyncio
async def test_runtime_adapter_selects_strategy_from_binding_without_cross_contamination() -> None:
    classic = _RecordingStrategy(result=RAGResult(context="classic"))
    experimental = _RecordingStrategy(result=RAGResult(context="experimental"))
    registry = RAGStrategyRegistry()
    registry.register("classic", classic)
    registry.register("experimental", experimental)
    adapter = _adapter(registry)

    first_result = await adapter.retrieve(
        binding=_binding("classic"),
        query="one",
    )
    second_result = await adapter.retrieve(
        binding=_binding("experimental"),
        query="two",
    )

    assert first_result.context == "classic"
    assert second_result.context == "experimental"
    assert [call[0].query for call in classic.calls] == ["one"]
    assert [call[0].query for call in experimental.calls] == ["two"]


@pytest.mark.asyncio
async def test_runtime_adapter_rejects_unknown_binding_strategy() -> None:
    registry = RAGStrategyRegistry()
    registry.register("classic", _RecordingStrategy())

    with pytest.raises(ValidationError, match="Unknown RAG strategy: agentic"):
        await _adapter(registry).retrieve(
            binding=_binding("agentic"),
            query="question",
            )


@pytest.mark.asyncio
async def test_runtime_adapter_attaches_embedding_failure_metadata_to_error() -> None:
    failure = EmbeddingProviderError(
        EmbeddingFailure(
            category="provider_rate_limit",
            safe_message="rate limited",
            upstream_status=429,
            upstream_error_code="rate_limit",
            retryable=True,
        )
    )
    strategy = _RecordingStrategy(error=failure)
    registry = RAGStrategyRegistry()
    registry.register("classic", strategy)
    binding = _binding()

    with pytest.raises(EmbeddingProviderError) as raised:
        await _adapter(registry).retrieve(
            binding=binding,
            query="question",
            )

    metadata = getattr(raised.value, "rag_metadata")
    assert metadata["failure_phase"] == "rag_query_embedding"
    assert metadata["embedding_error_category"] == "provider_rate_limit"
    assert metadata["upstream_status"] == 429
    assert metadata["upstream_error_code"] == "rate_limit"
    assert metadata["embedding_retryable"] is True
    assert metadata["vector_snapshot_id"] == str(binding.snapshot.id)
