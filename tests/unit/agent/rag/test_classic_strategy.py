from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.rag.contracts import RAGCapabilities, RAGRequest
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from shared.contracts.errors import ValidationError


class _Embedding:
    def __init__(self) -> None:
        self.queries: list[str] = []

    async def embed_query(self, text: str) -> list[float]:
        self.queries.append(text)
        return [0.1, 0.2, 0.3]


class _VectorSearch:
    def __init__(self, candidates) -> None:
        self.candidates = list(candidates)
        self.calls: list[dict] = []

    async def search(self, **kwargs):
        self.calls.append(dict(kwargs))
        return list(self.candidates)


def _chunk(document_id, content: str, score: float, *, page: int = 1):
    return (
        SimpleNamespace(
            id=uuid4(),
            document_id=document_id,
            content=content,
            page_number=page,
        ),
        score,
    )


@pytest.mark.asyncio
async def test_classic_preserves_final_query_filter_diversity_and_top_k() -> None:
    doc_a = uuid4()
    doc_b = uuid4()
    doc_c = uuid4()
    candidates = [
        _chunk(doc_a, "A1", 0.95),
        _chunk(doc_a, "A2", 0.91),
        _chunk(doc_b, "B1", 0.87, page=4),
        _chunk(doc_c, "C1", 0.40),
    ]
    embedding = _Embedding()
    vector = _VectorSearch(candidates)
    config = RAGRuntimeConfig(
        candidate_k=4,
        top_k=2,
        min_score=0.80,
        max_context_chunks=2,
        max_chunks_per_document=1,
        query_mode="conversation_context",
        history_turns=1,
    )
    request = RAGRequest(
        query="User: old question\nAssistant: old answer\nCurrent user message: Current question",
        config=config,
        vector_snapshot_id=uuid4(),
        snapshot_documents=(
            SimpleNamespace(document_id=doc_a, document_title="Document A"),
            SimpleNamespace(document_id=doc_b, document_title="Document B"),
        ),
    )

    result = await ClassicRAGStrategy().retrieve(
        request,
        RAGCapabilities(embedding=embedding, vector_search=vector),
    )

    assert embedding.queries == [request.query]
    assert vector.calls == [
        {
            "vector_snapshot_id": request.vector_snapshot_id,
            "embedding": [0.1, 0.2, 0.3],
            "limit": 4,
            "threshold": 0.0,
        }
    ]
    assert result.context is not None
    assert "A1" in result.context
    assert "A2" not in result.context
    assert "B1" in result.context
    assert [source.document_title for source in result.sources] == ["Document A", "Document B"]
    assert result.metrics["candidate_count"] == 4
    assert result.metrics["filtered_count"] == 3
    assert result.metrics["matched_chunks"] == 2
    assert result.metrics["context_chunks"] == 2
    assert result.metrics["best_score"] == 0.95


@pytest.mark.asyncio
async def test_classic_does_not_reinterpret_execution_query_policy() -> None:
    document_id = uuid4()
    embedding = _Embedding()
    vector = _VectorSearch([_chunk(document_id, "answer", 0.9)])
    final_query = (
        "User: prior question\n"
        "Assistant: prior answer\n"
        "Current user message: only this"
    )
    request = RAGRequest(
        query=final_query,
        config=RAGRuntimeConfig(
            query_mode="conversation_context",
            history_turns=10,
            candidate_k=1,
            top_k=1,
            max_context_chunks=1,
        ),
        vector_snapshot_id=uuid4(),
        snapshot_documents=(
            SimpleNamespace(document_id=document_id, document_title="Doc"),
        ),
    )

    await ClassicRAGStrategy().retrieve(
        request,
        RAGCapabilities(embedding=embedding, vector_search=vector),
    )

    assert embedding.queries == [final_query]


@pytest.mark.asyncio
async def test_classic_enforces_context_character_budget() -> None:
    document_id = uuid4()
    embedding = _Embedding()
    vector = _VectorSearch([_chunk(document_id, "x" * 1500, 0.9)])
    request = RAGRequest(
        query="question",
        config=RAGRuntimeConfig(
            candidate_k=1,
            top_k=1,
            max_context_chunks=1,
            max_context_chars=1000,
        ),
        vector_snapshot_id=uuid4(),
        snapshot_documents=(
            SimpleNamespace(document_id=document_id, document_title="Long document"),
        ),
    )

    result = await ClassicRAGStrategy().retrieve(
        request,
        RAGCapabilities(embedding=embedding, vector_search=vector),
    )

    assert result.context is not None
    assert len(result.context) == 1000
    assert result.metrics["context_chars"] == 1000


@pytest.mark.asyncio
async def test_classic_required_grounding_rejects_empty_retrieval() -> None:
    embedding = _Embedding()
    vector = _VectorSearch([])
    request = RAGRequest(
        query="question",
        config=RAGRuntimeConfig(grounding_policy="required"),
        vector_snapshot_id=uuid4(),
        snapshot_documents=(),
    )

    with pytest.raises(ValidationError, match="No relevant information"):
        await ClassicRAGStrategy().retrieve(
            request,
            RAGCapabilities(embedding=embedding, vector_search=vector),
        )


@pytest.mark.asyncio
async def test_classic_optional_grounding_returns_empty_context() -> None:
    embedding = _Embedding()
    vector = _VectorSearch([])
    request = RAGRequest(
        query="question",
        config=RAGRuntimeConfig(grounding_policy="optional"),
        vector_snapshot_id=uuid4(),
        snapshot_documents=(),
    )

    result = await ClassicRAGStrategy().retrieve(
        request,
        RAGCapabilities(embedding=embedding, vector_search=vector),
    )

    assert result.context is None
    assert result.sources == ()
    assert result.metrics["matched_chunks"] == 0
