"""Explicitly disable Knowledge retrieval while preserving the historical default."""

from modules.agent.application.interfaces.knowledge import (
    KnowledgeCapabilities,
    KnowledgeRequest,
    KnowledgeResult,
)


class NoKnowledgeStrategy:
    name = "none"

    async def retrieve(
        self,
        _request: KnowledgeRequest,
        _capabilities: KnowledgeCapabilities,
    ) -> KnowledgeResult:
        return KnowledgeResult(
            content=None,
            metadata={"knowledge_strategy": self.name},
        )


__all__ = ["NoKnowledgeStrategy"]
