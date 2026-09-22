from __future__ import annotations

from typing import Protocol


class ContextInvocation(Protocol):
    """Read-only Model Invocation facts relevant to a Context Manager algorithm."""

    @property
    def phase(self) -> str | None: ...

    @property
    def provider(self) -> str: ...

    @property
    def model(self) -> str: ...

    @property
    def delegated(self) -> bool: ...

    @property
    def has_active_tools(self) -> bool: ...
