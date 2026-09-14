from __future__ import annotations

from modules.agent.application.rag.registry import RAGStrategyRegistry
from modules.agent.application.rag.strategies.classic import ClassicRAGStrategy
from modules.agent.infra.adapters.langchain_embedding_factory import LangchainEmbeddingFactory
from modules.agent.infra.database.runtime_transaction_runner import AgentRuntimeTransactionRunner
from modules.agent.infra.database.runtime_vector_search_reader import AgentRuntimeVectorSearchReader
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter


def build_rag_strategy_registry() -> RAGStrategyRegistry:
    registry = RAGStrategyRegistry()
    registry.register("classic", ClassicRAGStrategy())
    return registry


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
