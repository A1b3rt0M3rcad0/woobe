from __future__ import annotations

from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter


class TransactionBoundedVectorSnapshotRAGMixin:
    """Compatibility holder for the frozen Knowledge runtime binding.

    Knowledge retrieval is no longer intercepted during preparation. The bound
    RAG runtime is consumed only through the ExecutionStrategy Knowledge facade.
    """

    _rag_runtime: RAGRuntimeAdapter | None = None

    def configure_rag_runtime(self, adapter: RAGRuntimeAdapter) -> None:
        self._rag_runtime = adapter
