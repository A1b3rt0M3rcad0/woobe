from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.infra.execution import transaction_bounded_rag as rag_module
from modules.agent.infra.execution.transaction_bounded_rag import (
    TransactionBoundedVectorSnapshotRAGMixin,
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


class _RAGRuntime(TransactionBoundedVectorSnapshotRAGMixin):
    def __init__(self, factory, reader) -> None:
        self._embedding_factory = factory
        self._vector_search_reader = reader
        self._encryption_key = "test-key"


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

    async def vector_reader(**kwargs):
        assert kwargs["vector_snapshot_id"] == snapshot_id
        assert kwargs["embedding"] == [0.1, 0.2, 0.3]

        async def sql_read():
            return [(chunk, 0.95)]

        return await guard.read(sql_read)

    runtime = _RAGRuntime(_EmbeddingFactory(client), vector_reader)
    agent = SimpleNamespace(
        id=agent_id,
        project_id=project_id,
        settings={
            "knowledge_version_id": str(knowledge_id),
            "runtime_config": {
                "rag": {
                    "top_k": 3,
                    "candidate_k": 5,
                    "max_chunks_per_document": 3,
                    "max_context_chunks": 3,
                    "max_context_chars": 4000,
                }
            },
        },
    )
    context = new_execution_context()
    context.execution_context = "playground"
    context.prepared_rag = {
        "knowledge": knowledge,
        "snapshot": snapshot,
        "provider_model": provider_model,
        "credential": credential,
        "snapshot_documents": snapshot_documents,
    }

    monkeypatch.setattr(rag_module, "decrypt_secret", lambda *_args: "embedding-key")
    token = current_execution.set(context)
    try:
        rag_context, sources = await runtime._load_rag_context(
            agent,
            "what is Woobe?",
            object(),
        )
    finally:
        current_execution.reset(token)

    assert client.calls == 1
    assert guard.write_calls == 0
    assert guard.read_calls == 1
    assert rag_context is not None
    assert "Woobe is the control plane." in rag_context
    assert len(sources) == 1
    assert sources[0].document_id == str(document_id)
    assert context.rag_metadata["vector_snapshot_id"] == str(snapshot_id)
