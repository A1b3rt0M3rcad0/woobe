from __future__ import annotations

from typing import Protocol

from modules.agent.application.strategy_sdk.model import (
    StrategyModelResult,
    StrategyPhase,
)


_TEXT_BLOCK_TYPES = {"", "text", "output_text"}
_INTERNAL_BLOCK_TYPES = {
    "reasoning",
    "reasoning_content",
    "thinking",
    "thought",
    "internal",
    "tool_use",
    "server_tool_call",
    "web_search_call",
}


def _public_result_text(result: StrategyModelResult | object) -> str:
    content = getattr(result, "content", None)
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""

    parts: list[str] = []
    for block in content:
        if isinstance(block, str):
            parts.append(block)
            continue
        if not isinstance(block, dict):
            continue
        block_type = str(block.get("type") or "").lower()
        if block_type in _INTERNAL_BLOCK_TYPES or block_type not in _TEXT_BLOCK_TYPES:
            continue
        for key in ("text", "content", "delta"):
            value = block.get(key)
            if isinstance(value, str):
                parts.append(value)
                break
    return "".join(parts)


def model_result_has_public_output(result: StrategyModelResult | object) -> bool:
    """Return whether a Model result contains user-facing output."""

    return bool(_public_result_text(result).strip())


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
