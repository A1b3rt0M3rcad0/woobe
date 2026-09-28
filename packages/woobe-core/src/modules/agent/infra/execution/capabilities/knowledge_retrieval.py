from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Mapping

from modules.agent.application.dtos.runtime_dtos import SourceInfo
from modules.agent.application.interfaces.knowledge import (
    KnowledgeConversation,
    KnowledgeMessage,
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


KnowledgeRetrieveFn = Callable[[str], Awaitable[Any]]


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalResult:
    """Normalized Knowledge result independent from the concrete retrieval strategy."""

    content: str | None
    sources: tuple[SourceInfo, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class KnowledgeRetrievalCapability:
    """Runtime-governed Knowledge access exposed to Strategy Runtime."""

    retrieve_fn: KnowledgeRetrieveFn | None
    query_mode: str = "conversation_context"
    history_turns: int = 3

    def __post_init__(self) -> None:
        if self.query_mode not in {"current_message", "conversation_context"}:
            raise ValueError(f"Unsupported Knowledge query mode: {self.query_mode}")
        if self.history_turns <= 0:
            raise ValueError("Knowledge history_turns must be positive")

    def build_query(self, conversation: KnowledgeConversation) -> str | None:
        current = _message_text(conversation.current_user_message)
        if current is None:
            return None

        if self.query_mode != "conversation_context":
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

        tail = conversational[-(self.history_turns * 2) :]
        if not tail:
            return current

        lines = [f"{role}: {content}" for role, content in tail]
        lines.append(f"Current user message: {current}")
        return "\n".join(lines)

    async def retrieve(self, *, query: str) -> KnowledgeRetrievalResult:
        if self.retrieve_fn is None or not query:
            return KnowledgeRetrievalResult(content=None)

        raw = await self.retrieve_fn(query)
        content = getattr(raw, "content", None)
        if content is None:
            content = getattr(raw, "context", None)

        raw_sources = getattr(raw, "sources", ()) or ()
        sources = tuple(
            source for source in raw_sources if isinstance(source, SourceInfo)
        )

        metadata: dict[str, Any] = {}
        metrics = getattr(raw, "metrics", None)
        if isinstance(metrics, Mapping):
            metadata.update(metrics)
        return KnowledgeRetrievalResult(
            content=content if isinstance(content, str) else None,
            sources=sources,
            metadata=metadata,
        )
