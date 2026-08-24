from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest

from modules.agent.application.interfaces.execution_context import current_execution
from modules.agent.composition.factories import ask_agent_runtime_factory
from modules.agent.domain.entities import Tool
from modules.agent.domain.enums import ToolStatus, ToolType
from modules.agent.infra.execution import agent_tool_runtime_gateway
from modules.agent.infra.execution.runtime_streaming import current_runtime_stream
from modules.network.application.runtime import InternalDelegationTool
from modules.network.infra.runtime.agent_invoker import ProjectRAIAgentInvoker


@pytest.mark.anyio
async def test_network_invoker_uses_public_transaction_bounded_agent_runtime(
    monkeypatch,
    settings,
) -> None:
    internal_tool_id = uuid4()
    agent_tool_id = uuid4()
    project_id = uuid4()
    agent_id = uuid4()
    network_id = uuid4()
    network_session_id = uuid4()
    network_execution_id = uuid4()
    network_invocation_id = uuid4()
    network_node_id = uuid4()
    trace_id = uuid4()
    delegated: list[dict] = []
    executed_agent_tools: list[tuple[object, dict]] = []
    streamed_events: list[tuple[str, dict]] = []
    prepared_agent_tool = Tool(
        id=agent_tool_id,
        project_id=project_id,
        agent_id=agent_id,
        name="customer_lookup",
        type=ToolType.HTTP,
        status=ToolStatus.ACTIVE,
        config={"url": "https://example.test/customer", "method": "GET"},
    )

    async def delegate(arguments: dict) -> dict:
        delegated.append(dict(arguments))
        return {"success": True, "result": "specialist-ok"}

    async def stream_handler(event_type: str, payload: dict) -> None:
        streamed_events.append((event_type, dict(payload)))

    class FakeToolRegistry:
        async def execute(self, tool, input_data):
            executed_agent_tools.append((tool, dict(input_data)))
            return SimpleNamespace(
                success=True,
                output={"customer": "active"},
                duration_ms=2,
                error=None,
            )

    class FakeTransactionBoundedRuntime:
        def __init__(
            self,
            *,
            transactions,
            llm_factory,
            encryption_key,
            tool_executor_factory,
        ) -> None:
            self._tool_executor_factory = tool_executor_factory
            self._runtime_tool_reader = None
            self._embedding_factory = None
            self._vector_search_reader = None
            self._execution_state_store = None

        def configure_rag_embedding_factory(self, factory) -> None:
            self._embedding_factory = factory

        def configure_runtime_tool_reader(self, reader) -> None:
            self._runtime_tool_reader = reader

        def configure_vector_search_reader(self, reader) -> None:
            self._vector_search_reader = reader

        def configure_execution_state_store(self, store) -> None:
            self._execution_state_store = store

        async def execute(self, input_dto):
            context = current_execution.get()
            assert context is not None
            assert context.project_id == project_id
            assert context.agent_id == agent_id
            assert context.network_execution_id == network_execution_id
            assert context.network_node_id == network_node_id
            assert context.internal_tool_name_to_id == {
                "delegate_to_specialist": str(internal_tool_id)
            }
            assert input_dto.metadata["source"] == "network_runtime"

            delegation_result = await self._tool_executor_factory(
                internal_tool_id,
                {"task": "answer the delegated task"},
            )
            assert delegation_result == {"success": True, "result": "specialist-ok"}

            context.prepared_tools = {str(agent_tool_id): prepared_agent_tool}
            agent_tool_result = await self._tool_executor_factory(
                agent_tool_id,
                {"query": "customer"},
            )
            assert agent_tool_result == {
                "success": True,
                "output": {"customer": "active"},
                "duration_ms": 2,
                "error": None,
            }

            channel = current_runtime_stream.get()
            assert channel is not None
            await channel.emit(
                "token",
                content="network-ok",
                visibility="assistant",
                channel="final",
                phase="final_response_generation",
                provider="custom",
                model="deepseek-v4-flash",
            )

            return SimpleNamespace(
                answer="network-ok",
                session_id=None,
                trace_id=trace_id,
                provider="custom",
                model="deepseek-v4-flash",
                usage=None,
                tool_calls=[],
                sources=[],
                parsed_output=None,
                output_parse_error=None,
            )

    monkeypatch.setattr(
        ask_agent_runtime_factory,
        "FrozenSnapshotStructuredOutputRuntime",
        FakeTransactionBoundedRuntime,
    )
    monkeypatch.setattr(
        agent_tool_runtime_gateway,
        "build_tool_runtime_registry",
        lambda **_kwargs: FakeToolRegistry(),
    )

    invoker = ProjectRAIAgentInvoker(settings, object())
    result = await invoker.invoke(
        project_id=project_id,
        agent_id=agent_id,
        release_id=None,
        snapshot_override={"provider": "custom", "model": "deepseek-v4-flash"},
        message="olá",
        agent_session_id=None,
        execution_context="playground",
        internal_tools=[
            InternalDelegationTool(
                id=internal_tool_id,
                name="delegate_to_specialist",
                description="Delegate to the specialist",
                handler=delegate,
            )
        ],
        network_context={
            "network_id": str(network_id),
            "network_session_id": str(network_session_id),
            "network_execution_id": str(network_execution_id),
            "network_invocation_id": str(network_invocation_id),
            "network_node_id": str(network_node_id),
            "depth": 0,
            "draft_revision": 4,
        },
        stream_handler=stream_handler,
    )

    assert result.answer == "network-ok"
    assert result.trace_id == trace_id
    assert result.provider == "custom"
    assert result.model == "deepseek-v4-flash"
    assert result.streamed_output is True
    assert delegated == [{"task": "answer the delegated task"}]
    assert executed_agent_tools == [
        (prepared_agent_tool, {"query": "customer"})
    ]
    assert any(
        event_type == "token" and payload.get("content") == "network-ok"
        for event_type, payload in streamed_events
    )
    assert current_execution.get() is None
    assert current_runtime_stream.get() is None
