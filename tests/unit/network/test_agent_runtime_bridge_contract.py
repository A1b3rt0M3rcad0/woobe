from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from modules.agent.runtime.runtime_streaming import current_runtime_stream
from modules.network.application.runtime import InternalDelegationTool
from modules.network.infra.runtime import agent_invoker as agent_invoker_module
from modules.network.infra.runtime.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor


_AGENT_TOOL_ID = UUID("00000000-0000-0000-0000-000000000101")
_DELEGATION_TOOL_ID = UUID("00000000-0000-0000-0000-000000000202")


class _Usage:
    def model_dump(self):
        return {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}


class _AgentOutput:
    def __init__(self, *, answer: str = "network final answer") -> None:
        self.answer = answer
        self.session_id = uuid4()
        self.trace_id = uuid4()
        self.provider = "openai"
        self.model = "gpt-test"
        self.usage = _Usage()
        self.tool_calls = []
        self.sources = []
        self.parsed_output = None
        self.output_parse_error = None


class _FakeGateway:
    instances = []

    def __init__(self, database, settings, executor=None) -> None:
        self.database = database
        self.settings = settings
        self.executor = executor
        self.read_ids = None
        self.executions = []
        type(self).instances.append(self)

    async def read_runtime_tools(self, tool_ids):
        self.read_ids = list(tool_ids)
        return [SimpleNamespace(id=tool_id) for tool_id in tool_ids]

    async def execute_tool(self, tool_id, input_data):
        self.executions.append((tool_id, dict(input_data)))
        return {
            "success": True,
            "output": {"value": "tool result"},
            "duration_ms": 1,
            "error": None,
        }


class _RuntimeBridgeUseCase:
    def __init__(
        self,
        *,
        session_factory,
        llm_factory,
        encryption_key,
        tool_executor_factory,
    ) -> None:
        self.tool_executor_factory = tool_executor_factory
        self.runtime_tool_reader = None

    def configure_rag_embedding_factory(self, _factory) -> None:
        return None

    def configure_runtime_tool_reader(self, reader) -> None:
        self.runtime_tool_reader = reader

    async def execute(self, input_dto):
        assert input_dto.metadata["source"] == "network_runtime"
        assert self.runtime_tool_reader is not None
        tools = await self.runtime_tool_reader([_AGENT_TOOL_ID])
        assert [tool.id for tool in tools] == [_AGENT_TOOL_ID]
        tool_result = await self.tool_executor_factory(
            _AGENT_TOOL_ID,
            {"query": "customer status"},
        )
        assert tool_result["success"] is True
        assert tool_result["output"] == {"value": "tool result"}
        return _AgentOutput()


class _StreamingBridgeUseCase(_RuntimeBridgeUseCase):
    async def execute(self, input_dto):
        channel = current_runtime_stream.get()
        assert channel is not None
        await channel.emit(
            "token",
            content="internal reasoning",
            visibility="internal",
            channel="reasoning",
            phase="response_generation",
        )
        await channel.emit(
            "token",
            content="network final answer",
            visibility="assistant",
            channel="final",
            phase="response_generation",
        )
        return _AgentOutput()


class _DelegationBridgeUseCase(_RuntimeBridgeUseCase):
    async def execute(self, input_dto):
        delegated = await self.tool_executor_factory(
            _DELEGATION_TOOL_ID,
            {"task": "resolve specialist task"},
        )
        assert delegated == {"success": True, "result": "specialist result"}
        return _AgentOutput(answer="root integrated specialist result")


def _patch_runtime(monkeypatch, use_case_cls) -> None:
    _FakeGateway.instances.clear()
    monkeypatch.setattr(agent_invoker_module, "AgentToolRuntimeGateway", _FakeGateway)
    monkeypatch.setattr(
        agent_invoker_module,
        "StructuredOutputAskAgentUseCase",
        use_case_cls,
    )
    monkeypatch.setattr(agent_invoker_module, "LangchainLLMFactory", lambda: object())
    monkeypatch.setattr(
        agent_invoker_module,
        "LangchainEmbeddingFactory",
        lambda: object(),
    )


def _invoker():
    engine = object()
    return ProjectRAIAgentInvoker(
        session_factory=SimpleNamespace(kw={"bind": engine}),
        settings=SimpleNamespace(encryption_key="test-encryption-key"),
        http_executor=object(),
    )


def _invoke_kwargs(*, internal_tools=None, stream_handler=None):
    return {
        "project_id": uuid4(),
        "agent_id": uuid4(),
        "release_id": None,
        "snapshot_override": {"provider": "openai", "model": "gpt-test"},
        "message": "answer through the network",
        "agent_session_id": uuid4(),
        "execution_context": "playground",
        "internal_tools": list(internal_tools or []),
        "network_context": {
            "network_id": str(uuid4()),
            "network_version_id": None,
            "network_session_id": str(uuid4()),
            "network_execution_id": str(uuid4()),
            "network_invocation_id": str(uuid4()),
            "parent_invocation_id": None,
            "network_node_id": str(uuid4()),
            "depth": 0,
        },
        "stream_handler": stream_handler,
    }


def test_network_worker_and_real_agent_invoker_are_importable() -> None:
    assert NetworkExecutionProcessor is not None
    assert ProjectRAIAgentInvoker is not None


@pytest.mark.asyncio
async def test_network_agent_bridge_returns_final_answer_and_uses_shared_agent_tool_runtime(
    monkeypatch,
) -> None:
    _patch_runtime(monkeypatch, _RuntimeBridgeUseCase)

    result = await _invoker().invoke(**_invoke_kwargs())

    assert result.answer == "network final answer"
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.usage == {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
    assert result.session_id is not None
    assert result.trace_id is not None
    assert result.streamed_output is False

    gateway = _FakeGateway.instances[-1]
    assert gateway.read_ids == [_AGENT_TOOL_ID]
    assert gateway.executions == [
        (_AGENT_TOOL_ID, {"query": "customer status"}),
    ]


@pytest.mark.asyncio
async def test_network_agent_bridge_streams_only_public_final_tokens(monkeypatch) -> None:
    _patch_runtime(monkeypatch, _StreamingBridgeUseCase)
    events = []

    async def stream_handler(event_type, payload):
        events.append((event_type, payload))

    result = await _invoker().invoke(
        **_invoke_kwargs(stream_handler=stream_handler)
    )

    assert result.answer == "network final answer"
    assert result.streamed_output is True
    assert [(event_type, payload["content"]) for event_type, payload in events] == [
        ("token", "network final answer"),
    ]


@pytest.mark.asyncio
async def test_network_internal_delegation_tool_executes_before_agent_tool_gateway(
    monkeypatch,
) -> None:
    _patch_runtime(monkeypatch, _DelegationBridgeUseCase)

    async def delegate(arguments):
        assert arguments == {"task": "resolve specialist task"}
        return {"success": True, "result": "specialist result"}

    internal_tool = InternalDelegationTool(
        id=_DELEGATION_TOOL_ID,
        name="delegate_specialist",
        description="Delegate to specialist",
        handler=delegate,
    )

    result = await _invoker().invoke(
        **_invoke_kwargs(internal_tools=[internal_tool])
    )

    assert result.answer == "root integrated specialist result"
    gateway = _FakeGateway.instances[-1]
    assert gateway.executions == []
