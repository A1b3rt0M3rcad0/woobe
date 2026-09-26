from __future__ import annotations

from types import SimpleNamespace

import pytest
from langchain_core.messages import HumanMessage, SystemMessage

from modules.agent.application.strategy_sdk import (
    StrategyContextContribution,
    StrategyToolSelectionMode,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.capabilities.tool_execution import (
    ToolExecutionCapability,
)
from modules.agent.infra.execution.strategy_runtime.context_manager import (
    RuntimeStrategyContextManager,
)
from modules.agent.infra.execution.strategy_runtime.runtime_state import (
    StrategyRuntimeState,
)
from modules.agent.infra.execution.strategy_runtime.tools import RuntimeStrategyTools


@pytest.mark.asyncio
async def test_knowledge_capability_normalizes_retrieval_result() -> None:
    async def retrieve(query: str):
        assert query == "runtime query"
        return SimpleNamespace(
            context="retrieved knowledge",
            sources=(),
            metrics={"retrieved_chunks": 2},
        )

    capability = KnowledgeRetrievalCapability(
        retrieve_fn=retrieve,
        default_query="runtime query",
    )

    result = await capability.retrieve()

    assert result.content == "retrieved knowledge"
    assert result.sources == ()
    assert result.metadata["retrieved_chunks"] == 2


@pytest.mark.asyncio
async def test_context_runtime_materializes_typed_knowledge_before_user_input() -> None:
    state = StrategyRuntimeState(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="question"),
        ]
    )
    runtime = RuntimeStrategyContextManager(
        capability=ContextAssemblyCapability(
            assembler=None,
            provider="test",
            model_name="test-model",
            pricing_snapshot=None,
        ),
        runtime_state=state,
    )
    runtime.set(
        StrategyContextContribution(
            key="knowledge.primary",
            source_type="KNOWLEDGE",
            content="answer from knowledge",
        )
    )

    assembled = await runtime.assemble()

    assert len(assembled.messages) == 3
    knowledge = assembled.messages[1]
    assert isinstance(knowledge, SystemMessage)
    assert "<context>\nanswer from knowledge\n</context>" in knowledge.content
    assert knowledge.additional_kwargs["woobe_context"]["source_type"] == "KNOWLEDGE"
    assert isinstance(assembled.messages[2], HumanMessage)


def test_runtime_tool_selection_rejects_tools_outside_authorized_mapping() -> None:
    capability = ToolExecutionCapability(
        execute_single_tool=lambda *_args: None,  # type: ignore[arg-type]
        tool_name_to_id={"search": "tool-id"},
    )
    runtime = RuntimeStrategyTools(
        capability=capability,
        runtime_state=StrategyRuntimeState(),
    )

    assert runtime.all().mode is StrategyToolSelectionMode.ALL
    assert runtime.none().mode is StrategyToolSelectionMode.NONE
    assert runtime.select("search").names == ("search",)

    with pytest.raises(ValueError, match="unauthorized or unknown"):
        runtime.select("admin")
