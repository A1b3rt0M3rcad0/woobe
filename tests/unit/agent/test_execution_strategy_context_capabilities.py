from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from uuid import uuid4

from modules.agent.application.context_managers.standard import (
    ProgrammableStandardContextAssembler,
)
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
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
async def test_context_compaction_is_owned_by_configured_manager() -> None:
    model = _SummaryModel()

    async def execute_single_tool(_tool_call, _tool_id):
        raise AssertionError("Context compaction must not execute Tools")

    messages = []
    for index in range(5):
        messages.append(
            HumanMessage(content=f"old-user-{index} " + ("u" * 500))
        )
        messages.append(
            AIMessage(content=f"old-assistant-{index} " + ("a" * 500))
        )
    messages.append(HumanMessage(content="current user question"))

    execution_context = new_execution_context()
    execution_context.run_id = uuid4()
    execution_context.project_id = uuid4()
    execution_context.context_policy = {
        "budget": {"max_input_units": 1500},
    }
    token = current_execution.set(execution_context)
    try:
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
                assembler=ProgrammableStandardContextAssembler(
                    compaction_keep_recent_messages=2,
                    compaction_target_units=256,
                ),
                provider="custom",
                model_name="summary-model",
                pricing_snapshot=None,
            ),
            recovery=StrategyRecoveryCapability(strategy_name="standard"),
        )
        built = build_strategy_context_from_capabilities(
            strategy=StandardExecutionStrategy(),
            capabilities=capabilities,
            messages=messages,
            initial_phase="response_generation",
            final_json_instruction=None,
        )

        inspection = built.context.context.inspect()
        assert inspection.pressure in {"HIGH", "CRITICAL"}

        compaction = await built.context.context.compact(
            phase="context_compaction",
        )

        assert compaction.changed is True
        assert compaction.upserted_keys == ("context.session.compaction",)
        contribution = built.runtime_state.context_contributions[
            "context.session.compaction"
        ]
        assert contribution.content == "Compact session summary"
        assert contribution.replaces_message_indexes
        assert contribution.metadata["operation"] == "summarize_replace"

        invocation = await built.context.context.assemble(
            tools=built.context.tools.none(),
            phase="response_generation",
        )
    finally:
        current_execution.reset(token)

    assert len(model.invocations) == 1
    serialized = str(invocation.messages)
    assert "Compact session summary" in serialized
    assert "old-user-0" not in serialized
    assert "current user question" in serialized
    assert [call["phase"] for call in built.runtime_state.execution.llm_calls] == [
        "context_compaction"
    ]



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
