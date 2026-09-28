from __future__ import annotations

from typing import Any, Protocol


class KnowledgeMessage(Protocol):
    """Minimal conversation message surface required by Knowledge query construction."""

    role: Any
    content: Any


class KnowledgeConversation(Protocol):
    """Read-only conversation surface required by the Knowledge capability."""

    @property
    def current_user_message(self) -> KnowledgeMessage | None: ...

    @property
    def history(self) -> tuple[KnowledgeMessage, ...]: ...


__all__ = [
    "KnowledgeConversation",
    "KnowledgeMessage",
]
