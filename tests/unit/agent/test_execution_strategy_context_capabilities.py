from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.infra.execution.capabilities.bundle import ExecutionCapabilities
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.recovery import StrategyRecoveryCapability
from modules.agent.infra.execution.capabilities.tool_execution import ToolExecutionCapability
from modules.agent.infra.execution.strategies.standard import StandardExecutionStrategy
from modules.agent.infra.execution.strategy_runtime.builder import (
    build_strategy_context_from_capabilities,
)


class _SummaryModel:
    def __init__(self) -> None:
        self.invocations = []

    async def ainvoke(self, messages):
        self.invocations.append(list(messages))
        return AIMessage(content="Compact session summary")


@pytest.mark.asyncio
async def test_context_summarize_is_explicit_and_does_not_mutate_context() -> None:
    model = _SummaryModel()

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Context summarization must not execute Tools")

    capabilities = ExecutionCapabilities(
        model=ModelInvocationCapability(
            model=model,
            provider="custom",
            model_name="summary-model",
        ),
        tools=ToolExecutionCapability(
            execute_single_tool=execute_single_tool,
            tool_name_to_id={},
        ),
        knowledge=KnowledgeRetrievalCapability(retrieve_fn=None),
        context=ContextAssemblyCapability(
            assembler=None,
            provider="custom",
            model_name="summary-model",
            pricing_snapshot=None,
        ),
        recovery=StrategyRecoveryCapability(strategy_name="standard"),
    )
    built = build_strategy_context_from_capabilities(
        strategy=StandardExecutionStrategy(),
        capabilities=capabilities,
        messages=[HumanMessage(content="Remember that the project uses Go.")],
        initial_phase="response_generation",
        final_json_instruction=None,
    )

    inspection = built.context.context.inspect()
    assert inspection.message_count == 1
    assert inspection.contribution_count == 0

    summary = await built.context.context.summarize(
        key="session.summary",
        target_units=256,
        phase="context_summarization",
    )

    assert summary.key == "session.summary"
    assert summary.source_type == "SESSION"
    assert summary.content == "Compact session summary"
    assert built.context.context.has("session.summary") is False
    assert len(built.runtime_state.messages) == 1
    assert [call["phase"] for call in built.runtime_state.execution.llm_calls] == [
        "context_summarization"
    ]

    built.context.context.set(summary)
    assert built.context.context.has("session.summary") is True



def test_strategy_conversation_exposes_real_bound_messages_read_only() -> None:
    model = _SummaryModel()

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Conversation inspection must not execute Tools")

    capabilities = ExecutionCapabilities(
        model=ModelInvocationCapability(
            model=model,
            provider="custom",
            model_name="conversation-model",
        ),
        tools=ToolExecutionCapability(
            execute_single_tool=execute_single_tool,
            tool_name_to_id={},
        ),
        knowledge=KnowledgeRetrievalCapability(retrieve_fn=None),
        context=ContextAssemblyCapability(
            assembler=None,
            provider="custom",
            model_name="conversation-model",
            pricing_snapshot=None,
        ),
        recovery=StrategyRecoveryCapability(strategy_name="standard"),
    )
    messages = [
        SystemMessage(content="Agent system instruction"),
        HumanMessage(content="Older user question"),
        AIMessage(content="Older assistant answer"),
        HumanMessage(content="Current user question"),
    ]
    built = build_strategy_context_from_capabilities(
        strategy=StandardExecutionStrategy(),
        capabilities=capabilities,
        messages=messages,
        initial_phase="response_generation",
        final_json_instruction=None,
    )

    conversation = built.context.conversation

    assert conversation.messages == tuple(messages)
    assert conversation.current_user_message is messages[-1]
    assert conversation.history == tuple(messages[1:3])
    assert conversation.system_messages == (messages[0],)
    assert conversation.assistant_messages == (messages[2],)
    assert conversation.last_assistant_message is messages[2]
