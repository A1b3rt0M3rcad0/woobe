from __future__ import annotations

from typing import Protocol

from modules.agent.application.strategy_sdk.model import (
    StrategyModelResult,
    StrategyPhase,
)


class StrategyOutput(Protocol):
    """Output validation/repair mechanisms controlled explicitly by a Strategy."""

    @property
    def json_required(self) -> bool: ...

    def has_public_output(self, result: StrategyModelResult) -> bool: ...

    def requires_repair(self, result: StrategyModelResult) -> bool: ...

    async def repair(
        self,
        result: StrategyModelResult,
        *,
        phase: StrategyPhase,
    ) -> StrategyModelResult: ...
