from __future__ import annotations

from dataclasses import dataclass

from modules.agent.application.strategy_sdk.tools import StrategyToolCall


@dataclass(frozen=True, slots=True)
class StrategyBootstrap:
    """Runtime-prepared bootstrap inputs that only the Strategy may act on."""

    initial_tool_call: StrategyToolCall | None = None
