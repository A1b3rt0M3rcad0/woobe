from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.agent.application.strategy_sdk.tools import StrategyToolSelection


class StrategyInvocation(Protocol):
    """Opaque, immutable Model invocation prepared by the Context boundary."""

    @property
    def invocation_id(self) -> UUID: ...

    @property
    def phase(self) -> str: ...

    @property
    def tools(self) -> StrategyToolSelection: ...
