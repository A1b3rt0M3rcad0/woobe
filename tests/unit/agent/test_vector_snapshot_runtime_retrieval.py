from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.rag import RAGBinding
from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from modules.agent.domain.vector_snapshot_entities import (
    VectorSnapshotChunk,
    VectorSnapshotDocument,
)
from modules.agent.infra.execution.rag import embedding_capability as embedding_module
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter


class _VectorSearch:
    def __init__(self, results) -> None:
        self.results = results
        self.calls: list[dict] = []

    async def search(self, **kwargs):
        self.calls.append(dict(kwargs))
        return list(self.results)


def _adapter(embedding_factory, vector_search) -> RAGRuntimeAdapter:
    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    return RAGRuntimeAdapter(
        registry=registry,
        embedding_factory=embedding_factory,
        vector_search=vector_search,
        encryption_key="test-key",
    )


@pytest.mark.asyncio
async def test_vector_snapshot_rag_uses_agent_runtime_config_and_bound_snapshot(monkeypatch):
    project_id = uuid4()
    agent_id = uuid4()
    knowledge_id = uuid4()
    credential_id = uuid4()
    provider_model_id = uuid4()
    document_id = uuid4()
    snapshot_id = uuid4()
    rag_config = RAGRuntimeConfig(
        candidate_k=9,
        top_k=1,
        min_score=0.72,
        max_context_chunks=1,
        max_chunks_per_document=1,
        query_mode="current_message",
    )

    knowledge = SimpleNamespace(id=knowledge_id, version="v2")
    snapshot = SimpleNamespace(
        id=snapshot_id,
        version="v3",
        snapshot_hash="immutable-hash",
        embedding_provider_model_id=provider_model_id,
        embedding_provider="openrouter",
        embedding_model="openai/text-embedding-3-small",
        embedding_dimensions=3,
    )
    provider_model = SimpleNamespace(
        id=provider_model_id,
        project_id=project_id,
        provider_credential_id=credential_id,
        metadata={"capability": "embedding"},
    )
    credential = SimpleNamespace(
        id=credential_id,
        project_id=project_id,
        encrypted_secret="encrypted",
        metadata={},
    )
    chunk = VectorSnapshotChunk(
        vector_snapshot_id=snapshot_id,
        project_id=project_id,
        collection_id=uuid4(),
        document_id=document_id,
        content="The contract renewal date is 2031-04-17.",
        content_hash="chunk-hash",
        chunk_index=0,
        page_number=4,
    )
    snapshot_document = VectorSnapshotDocument(
        vector_snapshot_id=snapshot_id,
        document_id=document_id,
        document_sha256="doc-hash",
        document_title="Contract A",
        file_name="contract-a.pdf",
        parser="PDF",
        status_at_build="READY",
        chunk_count=1,
    )

    embedding_client = MagicMock()
    embedding_client.aembed_query = AsyncMock(return_value=[0.1, 0.2, 0.3])
    embedding_factory = MagicMock()
    embedding_factory.create_embedding_client.return_value = embedding_client
    vector_search = _VectorSearch([(chunk, 0.91)])
    monkeypatch.setattr(embedding_module, "decrypt_secret", lambda *_args: "api-key")

    binding = RAGBinding(
        strategy=rag_config.strategy,
        config=rag_config,
        knowledge=knowledge,
        snapshot=snapshot,
        provider_model=provider_model,
        credential=credential,
        snapshot_documents=(snapshot_document,),
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
            "rag_runtime_config_source": "production",
            "retrieval_query_mode": rag_config.query_mode,
        },
    )
    result = await _adapter(embedding_factory, vector_search).retrieve(
        binding=binding,
        query="When does it renew?",
    )

    embedding_client.aembed_query.assert_awaited_once_with("When does it renew?")
    assert vector_search.calls == [
        {
            "vector_snapshot_id": snapshot_id,
            "embedding": [0.1, 0.2, 0.3],
            "limit": 9,
            "threshold": 0.0,
        }
    ]
    assert result.context is not None
    assert "2031-04-17" in result.context
    assert result.sources[0].document_title == "Contract A"
    assert result.sources[0].page_number == 4
    assert result.metrics is not None
    assert result.metrics["strategy"] == "classic"
    assert result.metrics["knowledge_version_id"] == str(knowledge_id)
    assert result.metrics["vector_snapshot_id"] == str(snapshot_id)
    assert result.metrics["snapshot_hash"] == "immutable-hash"
    assert result.metrics["rag_runtime_config"] == rag_config.model_dump()
    assert result.metrics["matched_chunks"] == 1
