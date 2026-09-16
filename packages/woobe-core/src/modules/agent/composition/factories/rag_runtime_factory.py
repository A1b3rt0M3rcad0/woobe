from __future__ import annotations

from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.runtime_vector_search_reader import AgentRuntimeVectorSearchReader
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter


_DEFAULT_RAG_STRATEGY = "classic"
_RAG_STRATEGY_DESCRIPTIONS = {
    "classic": (
        "Semantic retrieval using embeddings and vector search over the selected immutable "
        "Knowledge snapshot."
    ),
}


def _rag_strategy_display_name(name: str) -> str:
    words = name.replace("-", " ").replace("_", " ").split()
    label = " ".join(word.upper() if word.lower() == "rag" else word.title() for word in words)
    if not label:
        return "RAG"
    return label if label.lower().endswith(" rag") else f"{label} RAG"


def build_rag_strategy_registry() -> RAGStrategyRegistry:
    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    return registry


def list_rag_strategies() -> tuple[dict[str, object], ...]:
    """Return the backend-owned catalog of strategies registered in this runtime."""

    registry = build_rag_strategy_registry()
    return tuple(
        {
            "name": name,
            "display_name": _rag_strategy_display_name(name),
            "description": _RAG_STRATEGY_DESCRIPTIONS.get(
                name,
                "Registered RAG execution strategy available to Agent Knowledge runtime.",
            ),
            "is_default": name == _DEFAULT_RAG_STRATEGY,
        }
        for name in registry.names()
    )


def build_rag_runtime_adapter(
    transactions: AgentRuntimeTransactionRunner,
    *,
    encryption_key: str,
) -> RAGRuntimeAdapter:
    return RAGRuntimeAdapter(
        registry=build_rag_strategy_registry(),
        embedding_factory=LangchainEmbeddingFactory(),
        vector_search=AgentRuntimeVectorSearchReader(transactions),
        encryption_key=encryption_key,
    )
