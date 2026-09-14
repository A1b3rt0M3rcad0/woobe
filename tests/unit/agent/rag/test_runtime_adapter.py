from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.embedding_errors import (
    EmbeddingFailure,
    EmbeddingProviderError,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.rag.contracts import RAGResult
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


def _prepared_context():
    context = new_execution_context()
    context.execution_context = "production"
    context.agent_release_version = "r5"
    context.prepared_rag = {
        "knowledge": SimpleNamespace(id=uuid4(), version="kv5"),
        "snapshot": SimpleNamespace(
            id=uuid4(),
            version="vs8",
            snapshot_hash="hash-8",
            embedding_provider_model_id=uuid4(),
            embedding_provider="openai",
            embedding_model="text-embedding-test",
            embedding_dimensions=3,
        ),
        "provider_model": SimpleNamespace(metadata={}),
        "credential": SimpleNamespace(encrypted_secret="ciphertext", metadata={}),
        "snapshot_documents": [],
    }
    return context


def _adapter(registry: RAGStrategyRegistry) -> RAGRuntimeAdapter:
    return RAGRuntimeAdapter(
        registry=registry,
        embedding_factory=_UnusedEmbeddingFactory(),
        vector_search=_UnusedVectorSearch(),
        encryption_key="key",
    )


@pytest.mark.asyncio
async def test_runtime_adapter_defaults_missing_strategy_to_classic_and_merges_metrics() -> None:
    strategy = _RecordingStrategy()
    registry = RAGStrategyRegistry()
    registry.register("classic", strategy)
    agent = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {
                "rag": {
                    "top_k": 3,
                    "candidate_k": 4,
                    "max_context_chunks": 3,
                }
            },
        }
    )
    context = _prepared_context()
    token = current_execution.set(context)
    try:
        result = await _adapter(registry).retrieve(
            agent=agent,
            query="question",
            history=("history",),
        )
    finally:
        current_execution.reset(token)

    assert result.context == "context"
    request, _capabilities = strategy.calls[0]
    assert request.config.strategy == "classic"
    assert request.query == "question"
    assert request.history == ("history",)
    assert context.rag_metadata["strategy"] == "classic"
    assert context.rag_metadata["knowledge_version_id"] == str(
        context.prepared_rag["knowledge"].id
    )
    assert context.rag_metadata["vector_snapshot_id"] == str(
        context.prepared_rag["snapshot"].id
    )
    assert context.rag_metadata["rag_runtime_config"]["strategy"] == "classic"
    assert context.rag_metadata["rag_runtime_config_source"] == "production"
    assert context.rag_metadata["custom_metric"] == 7


@pytest.mark.asyncio
async def test_runtime_adapter_selects_strategy_per_agent_without_cross_contamination() -> None:
    classic = _RecordingStrategy(result=RAGResult(context="classic"))
    experimental = _RecordingStrategy(result=RAGResult(context="experimental"))
    registry = RAGStrategyRegistry()
    registry.register("classic", classic)
    registry.register("experimental", experimental)
    adapter = _adapter(registry)

    first = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {"rag": {"strategy": "classic"}},
        }
    )
    second = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {"rag": {"strategy": "experimental"}},
        }
    )

    first_context = _prepared_context()
    token = current_execution.set(first_context)
    try:
        first_result = await adapter.retrieve(agent=first, query="one", history=())
    finally:
        current_execution.reset(token)

    second_context = _prepared_context()
    token = current_execution.set(second_context)
    try:
        second_result = await adapter.retrieve(agent=second, query="two", history=())
    finally:
        current_execution.reset(token)

    assert first_result.context == "classic"
    assert second_result.context == "experimental"
    assert [call[0].query for call in classic.calls] == ["one"]
    assert [call[0].query for call in experimental.calls] == ["two"]
    assert first_context.rag_metadata["strategy"] == "classic"
    assert second_context.rag_metadata["strategy"] == "experimental"


@pytest.mark.asyncio
async def test_runtime_adapter_rejects_unknown_explicit_strategy() -> None:
    registry = RAGStrategyRegistry()
    registry.register("classic", _RecordingStrategy())
    agent = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {"rag": {"strategy": "agentic"}},
        }
    )
    context = _prepared_context()
    token = current_execution.set(context)
    try:
        with pytest.raises(ValidationError, match="Unknown RAG strategy: agentic"):
            await _adapter(registry).retrieve(agent=agent, query="question", history=())
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_runtime_adapter_requires_prepared_acceptance_binding() -> None:
    registry = RAGStrategyRegistry()
    registry.register("classic", _RecordingStrategy())
    agent = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {"rag": {}},
        }
    )
    context = new_execution_context()
    token = current_execution.set(context)
    try:
        with pytest.raises(ValidationError, match="not prepared during Agent Run acceptance"):
            await _adapter(registry).retrieve(agent=agent, query="question", history=())
    finally:
        current_execution.reset(token)


@pytest.mark.asyncio
async def test_runtime_adapter_skips_agents_without_knowledge_and_clears_metadata() -> None:
    registry = RAGStrategyRegistry()
    registry.register("classic", _RecordingStrategy())
    context = new_execution_context()
    context.rag_metadata = {"stale": True}
    token = current_execution.set(context)
    try:
        result = await _adapter(registry).retrieve(
            agent=SimpleNamespace(settings={}),
            query="question",
            history=(),
        )
    finally:
        current_execution.reset(token)

    assert result.context is None
    assert context.rag_metadata is None


@pytest.mark.asyncio
async def test_runtime_adapter_preserves_embedding_failure_metadata() -> None:
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
    agent = SimpleNamespace(
        settings={
            "knowledge_version_id": str(uuid4()),
            "runtime_config": {"rag": {}},
        }
    )
    context = _prepared_context()
    token = current_execution.set(context)
    try:
        with pytest.raises(EmbeddingProviderError):
            await _adapter(registry).retrieve(agent=agent, query="question", history=())
    finally:
        current_execution.reset(token)

    assert context.rag_metadata["failure_phase"] == "rag_query_embedding"
    assert context.rag_metadata["embedding_error_category"] == "provider_rate_limit"
    assert context.rag_metadata["upstream_status"] == 429
    assert context.rag_metadata["upstream_error_code"] == "rate_limit"
    assert context.rag_metadata["embedding_retryable"] is True
