from __future__ import annotations

from typing import Any, Protocol


class StrategyConversation(Protocol):
    """Read-only conversation view exposed to an Execution Strategy."""

    @property
    def messages(self) -> tuple[Any, ...]: ...

    @property
    def current_user_message(self) -> Any | None: ...

    @property
    def history(self) -> tuple[Any, ...]: ...

    @property
    def system_messages(self) -> tuple[Any, ...]: ...

    @property
    def assistant_messages(self) -> tuple[Any, ...]: ...

    @property
    def last_assistant_message(self) -> Any | None: ...
