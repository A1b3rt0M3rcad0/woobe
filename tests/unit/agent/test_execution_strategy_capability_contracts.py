from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyKnowledgeResult,
    StrategyToolSelection,
    StrategyToolSelectionMode,
)


def test_strategy_knowledge_result_exposes_found_state() -> None:
    assert StrategyKnowledgeResult(content=None).found is False
    assert StrategyKnowledgeResult(content="").found is False
    assert StrategyKnowledgeResult(content="knowledge").found is True


def test_strategy_tool_selection_represents_all_or_none() -> None:
    assert StrategyToolSelection(StrategyToolSelectionMode.ALL).mode is StrategyToolSelectionMode.ALL
    assert StrategyToolSelection(StrategyToolSelectionMode.NONE).mode is StrategyToolSelectionMode.NONE
