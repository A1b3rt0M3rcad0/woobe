from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.interfaces.rag import RAGBinding
from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from modules.agent.infra.execution.rag import embedding_capability as embedding_module
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter
from modules.agent.infra.execution.strategy_runtime.knowledge import (
    RuntimeStrategyKnowledge,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)


class _Guard:
    def __init__(self) -> None:
        self.write_calls = 0
        self.read_calls = 0
        self.active_reads = 0

    async def read(self, operation):
        self.read_calls += 1
        self.active_reads += 1
        try:
            return await operation()
        finally:
            self.active_reads -= 1


class _EmbeddingClient:
    def __init__(self, guard: _Guard) -> None:
        self.guard = guard
        self.calls = 0

    async def aembed_query(self, query: str):
        assert self.guard.active_reads == 0, (
            "embedding provider call must run outside the vector SQL read scope"
        )
        assert query == "what is Woobe?"
        self.calls += 1
        return [0.1, 0.2, 0.3]


class _EmbeddingFactory:
    def __init__(self, client: _EmbeddingClient) -> None:
        self.client = client

    def create_embedding_client(self, **kwargs):
        assert kwargs["provider"] == "openai"
        assert kwargs["model"] == "embedding-test"
        assert kwargs["api_key"] == "embedding-key"
        assert kwargs["dimensions"] == 3
        return self.client


class _VectorSearch:
    def __init__(self, guard: _Guard, snapshot_id, chunk) -> None:
        self.guard = guard
        self.snapshot_id = snapshot_id
        self.chunk = chunk

    async def search(self, **kwargs):
        assert kwargs["vector_snapshot_id"] == self.snapshot_id
        assert kwargs["embedding"] == [0.1, 0.2, 0.3]

        async def sql_read():
            return [(self.chunk, 0.95)]

        return await self.guard.read(sql_read)


@pytest.mark.asyncio
async def test_rag_embedding_is_external_and_vector_search_is_read_only(monkeypatch) -> None:
    guard = _Guard()
    client = _EmbeddingClient(guard)
    project_id = uuid4()
    agent_id = uuid4()
    knowledge_id = uuid4()
    snapshot_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    provider_model_id = uuid4()

    knowledge = SimpleNamespace(id=knowledge_id, version="kv1")
    snapshot = SimpleNamespace(
        id=snapshot_id,
        version="vs1",
        snapshot_hash="immutable-hash",
        embedding_provider_model_id=provider_model_id,
        embedding_provider="openai",
        embedding_model="embedding-test",
        embedding_dimensions=3,
    )
    provider_model = SimpleNamespace(metadata={})
    credential = SimpleNamespace(encrypted_secret="ciphertext", metadata={})
    snapshot_documents = [
        SimpleNamespace(document_id=document_id, document_title="Woobe docs")
    ]
    chunk = SimpleNamespace(
        id=chunk_id,
        document_id=document_id,
        content="Woobe is the control plane.",
        page_number=1,
    )

    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    adapter = RAGRuntimeAdapter(
        registry=registry,
        embedding_factory=_EmbeddingFactory(client),
        vector_search=_VectorSearch(guard, snapshot_id, chunk),
        encryption_key="test-key",
    )
    rag_config = RAGRuntimeConfig(
        top_k=3,
        candidate_k=5,
        max_chunks_per_document=3,
        max_context_chunks=3,
        max_context_chars=4000,
    )
    binding = RAGBinding(
        strategy=rag_config.strategy,
        config=rag_config,
        knowledge=knowledge,
        snapshot=snapshot,
        provider_model=provider_model,
        credential=credential,
        snapshot_documents=tuple(snapshot_documents),
        metadata={
            "strategy": rag_config.strategy,
            "knowledge_version_id": str(knowledge_id),
            "knowledge_version": knowledge.version,
            "vector_snapshot_id": str(snapshot_id),
            "vector_snapshot_version": snapshot.version,
            "snapshot_hash": snapshot.snapshot_hash,
            "embedding_provider_model_id": str(provider_model_id),
            "embedding_provider": snapshot.embedding_provider,
            "embedding_model": snapshot.embedding_model,
            "embedding_dimensions": snapshot.embedding_dimensions,
            "rag_runtime_config": rag_config.model_dump(),
            "rag_runtime_config_source": "draft",
            "retrieval_query_mode": rag_config.query_mode,
        },
    )
    context = new_execution_context()

    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "embedding-key")
    async def retrieve(query: str):
        return await adapter.retrieve(
            binding=binding,
            query=query,
        )

    state = StrategyRuntimeState()
    knowledge = RuntimeStrategyKnowledge(
        capability=KnowledgeRetrievalCapability(
            retrieve_fn=retrieve,
        ),
        runtime_state=state,
    )

    token = current_execution.set(context)
    try:
        result = await knowledge.retrieve(query="what is Woobe?")
    finally:
        current_execution.reset(token)

    assert client.calls == 1
    assert guard.write_calls == 0
    assert guard.read_calls == 1
    assert result.content is not None
    assert "Woobe is the control plane." in result.content
    assert len(result.sources) == 1
    assert result.sources[0].document_id == str(document_id)
    assert len(state.execution.knowledge_calls) == 1
    assert state.execution.knowledge_calls[0]["status"] == "success"
    assert context.rag_metadata["strategy"] == "classic"
    assert context.rag_metadata["vector_snapshot_id"] == str(snapshot_id)
