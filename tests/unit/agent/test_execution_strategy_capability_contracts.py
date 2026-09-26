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


def test_strategy_tool_selection_represents_all_none_and_explicit_modes() -> None:
    assert StrategyToolSelection(StrategyToolSelectionMode.ALL).names == ()
    assert StrategyToolSelection(StrategyToolSelectionMode.NONE).names == ()

    selection = StrategyToolSelection(
        StrategyToolSelectionMode.EXPLICIT,
        ("search", "fetch"),
    )
    assert selection.names == ("search", "fetch")


def test_explicit_tool_selection_requires_names() -> None:
    try:
        StrategyToolSelection(StrategyToolSelectionMode.EXPLICIT)
    except ValueError as exc:
        assert "at least one tool name" in str(exc)
    else:
        raise AssertionError("Expected explicit tool selection without names to fail")
