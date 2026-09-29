from __future__ import annotations

from modules.agent.application.dtos.rag_config_dtos import RAGRuntimeConfig
from modules.agent.application.interfaces.knowledge import (
    KnowledgeCapabilities,
    KnowledgeConversation,
    KnowledgeMessage,
    KnowledgeRequest,
    KnowledgeResult,
)


def _message_text(message: KnowledgeMessage | None) -> str | None:
    if message is None:
        return None
    content = message.content
    if isinstance(content, str):
        normalized = content.strip()
        return normalized or None
    if not isinstance(content, list):
        return None

    parts: list[str] = []
    for part in content:
        if isinstance(part, str) and part.strip():
            parts.append(part.strip())
            continue
        if not isinstance(part, dict):
            continue
        text = part.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())
    return "\n".join(parts) or None


def _build_query(
    conversation: KnowledgeConversation,
    *,
    query_mode: str,
    history_turns: int,
) -> str | None:
    current = _message_text(conversation.current_user_message)
    if current is None:
        return None

    if query_mode != "conversation_context":
        return current

    conversational: list[tuple[str, str]] = []
    for message in conversation.history:
        content = _message_text(message)
        if content is None:
            continue
        role = getattr(message.role, "value", message.role)
        if role == "user":
            conversational.append(("User", content))
        elif role == "assistant":
            conversational.append(("Assistant", content))

    tail = conversational[-(history_turns * 2) :]
    if not tail:
        return current

    lines = [f"{role}: {content}" for role, content in tail]
    lines.append(f"Current user message: {current}")
    return "\n".join(lines)


class RAGKnowledgeStrategy:
    """Default Knowledge algorithm backed by the configured RAG retrieval capability.

    The Strategy owns conversation-to-query policy. The RAG subsystem receives only
    the resulting query and remains responsible for retrieval mechanics.
    """

    name = "rag"

    async def retrieve(
        self,
        request: KnowledgeRequest,
        capabilities: KnowledgeCapabilities,
    ) -> KnowledgeResult:
        if not capabilities.available:
            return KnowledgeResult(
                content=None,
                metadata={"knowledge_strategy": self.name},
            )

        raw_rag = request.runtime_config.get("rag")
        config = RAGRuntimeConfig.model_validate(
            raw_rag if isinstance(raw_rag, dict) else {}
        )
        query = _build_query(
            request.conversation,
            query_mode=config.query_mode,
            history_turns=config.history_turns,
        )
        if not query:
            return KnowledgeResult(
                content=None,
                query=None,
                metadata={"knowledge_strategy": self.name},
            )

        result = await capabilities.retrieve(query=query)
        return KnowledgeResult(
            content=result.content,
            query=query,
            sources=result.sources,
            metadata={
                "knowledge_strategy": self.name,
                **dict(result.metadata),
            },
        )


__all__ = ["RAGKnowledgeStrategy"]
