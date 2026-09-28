from __future__ import annotations

from modules.agent.application.strategy_sdk import (
    StrategyExecutionError,
    StrategyKnowledgeResult,
    StrategyKnowledgeSource,
    StrategyToolResult,
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



def test_strategy_contracts_are_framework_neutral_data() -> None:
    source = StrategyKnowledgeSource(document_title="Doc", page_number=2)
    assert source.as_dict()["document_title"] == "Doc"

    tool_result = StrategyToolResult(
        tool_call_id="call-1",
        tool_name="lookup",
        arguments={"id": "123"},
        output={"value": 1},
        success=True,
    )
    assert tool_result.tool_name == "lookup"
    assert tool_result.success is True

    assert issubclass(StrategyExecutionError, RuntimeError)
