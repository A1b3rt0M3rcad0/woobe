from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from modules.agent.application.strategy_sdk import StrategyToolSelection


@dataclass(frozen=True, slots=True)
class RuntimeStrategyInvocation:
    """Runtime-owned materialization of an opaque Strategy invocation."""

    invocation_id: UUID
    phase: str
    tools: StrategyToolSelection
    messages: tuple[Any, ...]
    snapshot: Any | None = None
