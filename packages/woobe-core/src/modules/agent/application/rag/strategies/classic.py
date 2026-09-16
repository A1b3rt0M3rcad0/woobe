from __future__ import annotations

from typing import Any
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.rag.contracts import RAGCapabilities, RAGRequest, RAGResult
from shared.contracts.errors import ValidationError


def build_retrieval_query(
    query: str,
    history: tuple[Any, ...],
    *,
    query_mode: str,
    history_turns: int,
) -> str:
    if query_mode != "conversation_context" or not history:
        return query

    conversational: list[tuple[str, str]] = []
    for message in history:
        content = getattr(message, "content", None)
        if not isinstance(content, str) or not content.strip():
            continue
        class_name = type(message).__name__
        if class_name == "HumanMessage":
            conversational.append(("User", content.strip()))
        elif class_name == "AIMessage":
            conversational.append(("Assistant", content.strip()))

    tail = conversational[-(history_turns * 2) :]
    if not tail:
        return query

    lines = [f"{role}: {content}" for role, content in tail]
    lines.append(f"Current user message: {query}")
    return "\n".join(lines)


class ClassicRAGStrategy:
    """Current Woobe vector retrieval behavior behind the RAG Strategy contract."""

    async def retrieve(
        self,
        request: RAGRequest,
        capabilities: RAGCapabilities,
    ) -> RAGResult:
        config = request.config
        retrieval_query = build_retrieval_query(
            request.query,
            request.history,
            query_mode=config.query_mode,
            history_turns=config.history_turns,
        )

        query_embedding = await capabilities.embedding.embed_query(retrieval_query)
        candidates = await capabilities.vector_search.search(
            vector_snapshot_id=request.vector_snapshot_id,
            embedding=query_embedding,
            limit=config.candidate_k,
            threshold=0.0,
        )

        candidate_scores = [round(float(score), 4) for _, score in candidates]
        filtered = (
            candidates
            if config.min_score is None
            else [
                (chunk, score)
                for chunk, score in candidates
                if float(score) >= config.min_score
            ]
        )

        selected: list[tuple[Any, float]] = []
        per_document: dict[UUID, int] = {}
        for chunk, score in filtered:
            count = per_document.get(chunk.document_id, 0)
            if count >= config.max_chunks_per_document:
                continue
            selected.append((chunk, score))
            per_document[chunk.document_id] = count + 1
            if len(selected) >= config.top_k:
                break

        document_titles = {
            document.document_id: document.document_title
            for document in request.snapshot_documents
        }
        sources: list[SourceInfo] = []
        context_chunks: list[str] = []
        context_chars = 0

        for chunk, score in selected[: config.max_context_chunks]:
            title = document_titles.get(chunk.document_id)
            prefix = f"[{len(context_chunks) + 1}]"
            if title:
                prefix += f" {title}"
            if chunk.page_number is not None:
                prefix += f" · page {chunk.page_number}"

            block = f"{prefix}\n{chunk.content}"
            remaining = config.max_context_chars - context_chars
            if remaining <= 0:
                break
            if len(block) > remaining:
                block = block[:remaining]

            context_chunks.append(block)
            context_chars += len(block)
            sources.append(
                SourceInfo(
                    document_id=str(chunk.document_id),
                    document_title=title,
                    chunk_id=str(chunk.id),
                    page_number=chunk.page_number,
                    score=round(float(score), 4),
                    content_preview=chunk.content[:200],
                )
            )

        metrics = {
            "retrieval_query_mode": config.query_mode,
            "candidate_count": len(candidates),
            "best_score": candidate_scores[0] if candidate_scores else None,
            "top_scores": candidate_scores[:10],
            "filtered_count": len(filtered),
            "matched_chunks": len(selected),
            "context_chunks": len(sources),
            "context_chars": context_chars,
        }

        if not context_chunks:
            if config.grounding_policy == "required":
                raise ValidationError(
                    "No relevant information was found in the configured knowledge version"
                )
            return RAGResult(context=None, metrics=metrics)

        return RAGResult(
            context="\n\n".join(context_chunks),
            sources=tuple(sources),
            metrics=metrics,
        )
