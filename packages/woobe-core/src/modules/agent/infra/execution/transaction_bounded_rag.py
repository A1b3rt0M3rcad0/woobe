from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Protocol, cast

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.infra.execution.rag.runtime_adapter import RAGRuntimeAdapter
from shared.contracts.errors import ValidationError

_rag_history_context: ContextVar[list[Any]] = ContextVar(
    "transaction_bounded_rag_history_context",
    default=[],
)


class _RAGSuper(Protocol):
    async def _prepare(self, input_dto: Any) -> Any: ...
    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]: ...


class TransactionBoundedVectorSnapshotRAGMixin:
    """Bridge Agent execution to the strategy-driven RAG runtime subsystem."""

    _rag_runtime: RAGRuntimeAdapter | None = None

    def configure_rag_runtime(self, adapter: RAGRuntimeAdapter) -> None:
        self._rag_runtime = adapter

    async def _prepare(self, input_dto: Any) -> Any:
        token = _rag_history_context.set([])
        try:
            parent = cast(_RAGSuper, super())
            return await parent._prepare(input_dto)
        finally:
            _rag_history_context.reset(token)

    async def _load_history(self, message_repo: Any, session: Any) -> list[Any]:
        parent = cast(_RAGSuper, super())
        history = await parent._load_history(message_repo, session)
        _rag_history_context.set(history)
        return history

    async def _load_rag_context(
        self,
        agent: Any,
        query: str,
        transactions: Any,
    ) -> tuple[str | None, list[SourceInfo]]:
        del transactions
        if self._rag_runtime is None:
            settings = getattr(agent, "settings", None)
            if not isinstance(settings, dict) or not settings.get("knowledge_version_id"):
                context = current_execution.get()
                if context is not None:
                    context.rag_metadata = None
                return None, []
            raise ValidationError("RAG runtime is not configured")

        result = await self._rag_runtime.retrieve(
            agent=agent,
            query=query,
            history=tuple(_rag_history_context.get()),
        )
        return result.context, list(result.sources)
