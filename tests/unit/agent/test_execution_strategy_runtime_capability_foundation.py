from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from modules.agent.application.context_managers.standard import StandardContextManager
from modules.agent.application.interfaces.execution_context import (
    current_execution,
    new_execution_context,
)
from modules.agent.application.rag.knowledge_strategy import RAGKnowledgeStrategy
from modules.agent.application.strategy_sdk import (
    StrategyContextContribution,
    StrategyKnowledgeResult,
    StrategyMessage,
    StrategyMessageRole,
    StrategyModelResult,
    StrategyToolSelection,
    StrategyToolSelectionMode,
)
from modules.agent.infra.execution.capabilities.context_assembly import (
    ContextAssemblyCapability,
)
from modules.agent.infra.execution.capabilities.knowledge_retrieval import (
    KnowledgeRetrievalCapability,
)
from modules.agent.infra.execution.capabilities.model_invocation import (
    ModelInvocationCapability,
)
from modules.agent.infra.execution.capabilities.tool_execution import (
    ToolExecutionCapability,
)
from modules.agent.infra.execution.strategy_runtime.context_manager import (
    RuntimeStrategyContextManager,
)
from modules.agent.infra.execution.strategy_runtime.knowledge import (
    RuntimeStrategyKnowledge,
)
from modules.agent.infra.execution.strategy_runtime.invocation import (
    RuntimeStrategyInvocation,
)
from modules.agent.infra.execution.strategy_runtime.model import RuntimeStrategyModel
from modules.agent.infra.execution.strategy_runtime.output import RuntimeStrategyOutput
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
    )

    result = await capability.retrieve(query="runtime query")

    assert result.content == "retrieved knowledge"
    assert result.sources == ()
    assert result.metadata["retrieved_chunks"] == 2


class _Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    async def emit(self, event_type: str, payload: dict) -> None:
        self.events.append((event_type, payload))


@pytest.mark.asyncio
async def test_strategy_knowledge_records_started_completed_and_execution_evidence() -> None:
    async def retrieve(query: str):
        assert query == "runtime query"
        return SimpleNamespace(
            context="retrieved knowledge",
            sources=(),
            metrics={"retrieved_chunks": 1},
        )

    state = StrategyRuntimeState()
    runtime = RuntimeStrategyKnowledge(
        capability=KnowledgeRetrievalCapability(
            retrieve_fn=retrieve,
        ),
        runtime_state=state,
        strategy=RAGKnowledgeStrategy(),
    )
    recorder = _Recorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    token = current_execution.set(context)
    try:
        result = await runtime.retrieve(conversation=SimpleNamespace(
            current_user_message=StrategyMessage(
                id=None, role=StrategyMessageRole.USER, content="runtime query",
            ),
            history=(),
        ))
    finally:
        current_execution.reset(token)

    assert result.content == "retrieved knowledge"
    assert [event for event, _payload in recorder.events] == [
        "knowledge.retrieval.started",
        "knowledge.retrieval.completed",
    ]
    assert len(state.execution.knowledge_calls) == 1
    assert state.execution.knowledge_calls[0]["status"] == "success"
    assert state.execution.knowledge_calls[0]["query"] == "runtime query"
    assert state.execution.timeline[0]["kind"] == "knowledge"


@pytest.mark.asyncio
async def test_strategy_knowledge_records_failed_retrieval_before_reraising() -> None:
    async def retrieve(_query: str):
        error = RuntimeError("retrieval unavailable")
        setattr(error, "rag_metadata", {"strategy": "classic"})
        raise error

    state = StrategyRuntimeState()
    runtime = RuntimeStrategyKnowledge(
        capability=KnowledgeRetrievalCapability(
            retrieve_fn=retrieve,
        ),
        runtime_state=state,
        strategy=RAGKnowledgeStrategy(),
    )
    recorder = _Recorder()
    context = new_execution_context()
    context.run_event_recorder = recorder
    token = current_execution.set(context)
    try:
        with pytest.raises(RuntimeError, match="retrieval unavailable"):
            await runtime.retrieve(
                conversation=SimpleNamespace(
                    current_user_message=StrategyMessage(
                        id=None, role=StrategyMessageRole.USER, content="runtime query",
                    ),
                    history=(),
                ),
            )
    finally:
        current_execution.reset(token)

    assert [event for event, _payload in recorder.events] == [
        "knowledge.retrieval.started",
        "knowledge.retrieval.failed",
    ]
    assert len(state.execution.knowledge_calls) == 1
    call = state.execution.knowledge_calls[0]
    assert call["status"] == "error"
    assert call["error"] == "retrieval unavailable"
    assert call["metadata"]["strategy"] == "classic"
    assert state.execution.timeline[0]["kind"] == "knowledge"


@pytest.mark.asyncio
async def test_context_manager_materializes_typed_knowledge_before_user_input() -> None:
    state = StrategyRuntimeState(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="question"),
        ]
    )
    runtime = RuntimeStrategyContextManager(
        capability=ContextAssemblyCapability(
            manager=StandardContextManager(),
            provider="test",
            model_name="test-model",
            pricing_snapshot=None,
        ),
        runtime_state=state,
    )
    runtime.include_knowledge(
        StrategyKnowledgeResult(
            content="answer from knowledge",
        )
    )
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    token = current_execution.set(context)
    try:
        assembled = await runtime.prepare(
            tools=StrategyToolSelection(mode=StrategyToolSelectionMode.NONE),
        )
    finally:
        current_execution.reset(token)

    assert len(assembled.messages) == 3
    knowledge = assembled.messages[1]
    assert isinstance(knowledge, SystemMessage)
    assert "<context>\nanswer from knowledge\n</context>" in knowledge.content
    assert knowledge.additional_kwargs["woobe_context"]["source_type"] == "KNOWLEDGE"
    assert isinstance(assembled.messages[2], HumanMessage)


@pytest.mark.asyncio
async def test_context_manager_scopes_tool_instructions_to_selected_invocation() -> None:
    state = StrategyRuntimeState(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="question"),
        ]
    )
    runtime = RuntimeStrategyContextManager(
        capability=ContextAssemblyCapability(
            manager=StandardContextManager(),
            provider="test",
            model_name="test-model",
            pricing_snapshot=None,
            tool_definitions=(
                {
                    "type": "function",
                    "function": {
                        "name": "search",
                        "description": "Search",
                        "parameters": {"type": "object"},
                    },
                },
            ),
        ),
        runtime_state=state,
    )
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    token = current_execution.set(context)
    try:
        without_tools = await runtime.prepare(
            tools=StrategyToolSelection(mode=StrategyToolSelectionMode.NONE),
        )
        with_tools = await runtime.prepare(
            tools=StrategyToolSelection(mode=StrategyToolSelectionMode.ALL),
        )
    finally:
        current_execution.reset(token)

    without_text = "\n".join(
        str(message.content)
        for message in without_tools.messages
        if isinstance(message, SystemMessage)
    )
    with_text = "\n".join(
        str(message.content)
        for message in with_tools.messages
        if isinstance(message, SystemMessage)
    )

    assert "complete and authoritative" not in without_text
    assert "Tool grounding rules" not in without_text
    assert "complete and authoritative" in with_text
    assert "Tool grounding rules" in with_text


def test_runtime_state_assigns_deterministic_unique_ids_to_base_messages() -> None:
    messages = [
        HumanMessage(content="same"),
        HumanMessage(content="same"),
        HumanMessage(content="different"),
    ]

    first = StrategyRuntimeState(messages=messages)
    second = StrategyRuntimeState(messages=messages)

    first_ids = [message.id for message in first.messages]
    second_ids = [message.id for message in second.messages]

    assert first_ids == second_ids
    assert all(first_ids)
    assert len(set(first_ids)) == len(first_ids)


@pytest.mark.asyncio
async def test_context_manager_applies_compaction_replacements_by_message_id() -> None:
    state = StrategyRuntimeState(
        messages=[
            SystemMessage(content="system"),
            HumanMessage(content="first"),
            HumanMessage(content="second"),
        ]
    )
    first_user = state.messages[1]
    state.context_contributions["summary.session"] = StrategyContextContribution(
        key="summary.session",
        source_type="SESSION",
        content="session summary",
    )
    state.context_replacements["summary.session"] = (str(first_user.id),)

    runtime = RuntimeStrategyContextManager(
        capability=ContextAssemblyCapability(
            manager=StandardContextManager(),
            provider="test",
            model_name="test-model",
            pricing_snapshot=None,
        ),
        runtime_state=state,
    )
    context = new_execution_context()
    context.run_id = uuid4()
    context.project_id = uuid4()
    token = current_execution.set(context)
    try:
        assembled = await runtime.prepare(
            tools=StrategyToolSelection(mode=StrategyToolSelectionMode.NONE),
        )
    finally:
        current_execution.reset(token)

    contents = [str(message.content) for message in assembled.messages]
    assert "first" not in contents
    assert "second" in contents
    assert "session summary" in contents


def test_runtime_tools_exposes_only_all_or_none() -> None:
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
    assert not hasattr(runtime, "select")


def test_runtime_model_binds_all_authorized_tools_or_none() -> None:
    definitions = [
        {
            "type": "function",
            "function": {
                "name": "search",
                "description": "Search",
                "parameters": {"type": "object"},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write",
                "description": "Write",
                "parameters": {"type": "object"},
            },
        },
    ]

    class _BindableModel:
        def __init__(self) -> None:
            self.bound: list[list[dict]] = []

        def bind_tools(self, tools, *, tool_choice):
            assert tool_choice == "auto"
            self.bound.append(list(tools))
            return SimpleNamespace(bound_tools=list(tools))

    model = _BindableModel()
    base = ModelInvocationCapability(
        model=model,
        provider="test",
        model_name="test-model",
    )
    runtime = RuntimeStrategyModel(
        capability=base,
        runtime_state=StrategyRuntimeState(),
        final_model=None,
        final_model_factory=None,
        tool_definitions=definitions,
    )

    all_capability = runtime._capability_for_tools(
        StrategyToolSelection(StrategyToolSelectionMode.ALL)
    )
    none_capability = runtime._capability_for_tools(
        StrategyToolSelection(StrategyToolSelectionMode.NONE)
    )

    assert model.bound == [definitions]
    assert all_capability.model.bound_tools == definitions
    assert none_capability is base



@pytest.mark.asyncio
async def test_strategy_output_repair_delegates_inference_to_model_runtime() -> None:
    class _Context:
        def __init__(self) -> None:
            self.calls = []

        def assemble(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                invocation_id=uuid4(),
                messages=tuple(kwargs["messages"]),
                snapshot=None,
            )

    class _Model:
        def __init__(self) -> None:
            self.invocations = []

        async def invoke_structured_repair(self, invocation):
            self.invocations.append(invocation)
            return StrategyModelResult(content='{"ok": true}')

    context = _Context()
    model = _Model()
    output = RuntimeStrategyOutput(
        runtime_state=StrategyRuntimeState(),
        json_enabled=True,
        schema={"type": "object"},
        clean_json_answer=lambda value: value,
        context_capability=context,  # type: ignore[arg-type]
        model_capabilities=model,
    )

    result = await output.repair(
        StrategyModelResult(content="not-json"),
        phase="json_repair",
    )

    assert result.content == '{"ok": true}'
    assert len(context.calls) == 1
    assert context.calls[0]["tool_selection_mode"] == "none"
    assert len(model.invocations) == 1
    assert model.invocations[0].phase == "json_repair"


@pytest.mark.asyncio
async def test_model_runtime_owns_structured_repair_model_invocation() -> None:
    calls = []

    async def invoke(**kwargs):
        calls.append(kwargs)
        return AIMessage(content='{"ok": true}'), {
            "call_id": "repair-1",
            "call_index": kwargs["call_index"],
            "phase": kwargs["phase"],
            "occurred_at": "2026-09-28T00:00:00+00:00",
            "status": "success",
        }

    repair_model = object()
    state = StrategyRuntimeState()
    runtime = RuntimeStrategyModel(
        capability=ModelInvocationCapability(
            model=object(),
            provider="test",
            model_name="test-model",
            invoke_fn=invoke,
        ),
        runtime_state=state,
        final_model=None,
        final_model_factory=None,
        structured_repair_model_factory=lambda: repair_model,
    )
    invocation = RuntimeStrategyInvocation(
        invocation_id=uuid4(),
        phase="json_repair",
        tools=StrategyToolSelection(StrategyToolSelectionMode.NONE),
        messages=(HumanMessage(content="repair this"),),
        snapshot=None,
    )

    result = await runtime.invoke_structured_repair(invocation)

    assert result.content == '{"ok": true}'
    assert calls[0]["model"] is repair_model
    assert state.last_model_message.content == '{"ok": true}'
    assert state.execution.result.content == '{"ok": true}'
    assert state.execution.llm_calls[-1]["phase"] == "json_repair"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mode", "expected"),
    [
        ("current_message", "current\nquestion"),
        (
            "conversation_context",
            "User: recent\nAssistant: reply\nCurrent user message: current\nquestion",
        ),
    ],
)
async def test_knowledge_strategy_owns_query_mode_history_limit_and_text_extraction(
    mode,
    expected,
):
    def message(role, content):
        return StrategyMessage(id=None, role=role, content=content)

    conversation = SimpleNamespace(
        current_user_message=message(
            StrategyMessageRole.USER,
            [{"type": "text", "text": " current "}, "question", {"image_url": "ignored"}],
        ),
        history=(
            message(StrategyMessageRole.USER, "old"),
            message(StrategyMessageRole.ASSISTANT, "old reply"),
            message(StrategyMessageRole.USER, "recent"),
            message(StrategyMessageRole.SYSTEM, "excluded"),
            message(StrategyMessageRole.ASSISTANT, "reply"),
            message(StrategyMessageRole.TOOL, "excluded"),
        ),
    )
    captured: list[str] = []

    async def retrieve(query: str):
        captured.append(query)
        return SimpleNamespace(context=None, sources=(), metrics={})

    runtime = RuntimeStrategyKnowledge(
        capability=KnowledgeRetrievalCapability(retrieve_fn=retrieve),
        runtime_state=StrategyRuntimeState(),
        strategy=RAGKnowledgeStrategy(),
        runtime_config={
            "rag": {
                "query_mode": mode,
                "history_turns": 1,
            }
        },
    )
    await runtime.retrieve(conversation=conversation)
    assert captured == [expected]


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [None, "   ", [{"image_url": "image"}]])
async def test_knowledge_skips_retrieval_without_current_text(content):
    async def retrieve(_query):
        pytest.fail("Empty current input must not trigger retrieval")

    runtime = RuntimeStrategyKnowledge(
        capability=KnowledgeRetrievalCapability(retrieve_fn=retrieve),
        runtime_state=StrategyRuntimeState(),
        strategy=RAGKnowledgeStrategy(),
    )
    result = await runtime.retrieve(conversation=SimpleNamespace(
        current_user_message=(
            StrategyMessage(id=None, role=StrategyMessageRole.USER, content=content)
            if content is not None else None
        ),
        history=(),
    ))
    assert not result.found
    assert result.query is None


def test_execution_context_surface_does_not_expose_storage_primitives():
    from modules.agent.application.strategy_sdk import StrategyContextManager

    for name in ("has", "set", "remove"):
        assert not hasattr(StrategyContextManager, name)
        assert not hasattr(RuntimeStrategyContextManager, name)
