from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest

from modules.agent.entrypoint import current_execution, current_runtime_stream
from modules.network.application.runtime import InternalDelegationTool
from modules.network.infra.runtime import agent_invoker as agent_invoker_module
from modules.network.infra.runtime.agent_invoker import ProjectRAIAgentInvoker
from modules.network.infra.workers.execution_worker import NetworkExecutionProcessor


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


class _RuntimeBridgeUseCase:
    async def execute(self, input_dto):
        assert input_dto.metadata["source"] == "network_runtime"
        return _AgentOutput()


class _StreamingBridgeUseCase(_RuntimeBridgeUseCase):
    async def execute(self, input_dto):
        assert input_dto.metadata["source"] == "network_runtime"
        channel = current_runtime_stream.get()
        assert channel is not None
        await channel.emit(
            "token",
            content="internal reasoning",
            visibility="internal",
            channel="reasoning",
            phase="response_generation",
        )
        for content in ("network ", "final ", "answer"):
            await channel.emit(
                "token",
                content=content,
                visibility="assistant",
                channel="final",
                phase="response_generation",
            )
        return _AgentOutput()


class _DelegationBridgeUseCase(_RuntimeBridgeUseCase):
    async def execute(self, input_dto):
        assert input_dto.metadata["source"] == "network_runtime"
        context = current_execution.get()
        assert context is not None
        assert context.internal_tool_handlers is not None
        delegated = await context.internal_tool_handlers[_DELEGATION_TOOL_ID](
            {"task": "resolve specialist task"}
        )
        assert delegated == {"success": True, "result": "specialist result"}
        return _AgentOutput(answer="root integrated specialist result")


def _patch_runtime(monkeypatch, use_case_cls):
    captured = {"build_calls": 0}

    def build_internal_agent_runtime(
        settings,
        http_executor,
        *,
        internal_tool_handlers=None,
    ):
        captured["build_calls"] += 1
        captured["settings"] = settings
        captured["http_executor"] = http_executor
        captured["internal_tool_handlers"] = dict(internal_tool_handlers or {})
        return use_case_cls()

    monkeypatch.setattr(
        agent_invoker_module,
        "build_internal_agent_runtime",
        build_internal_agent_runtime,
    )
    return captured


def _invoker():
    settings = SimpleNamespace(encryption_key="test-encryption-key")
    http_executor = object()
    return (
        ProjectRAIAgentInvoker(
            settings=settings,
            http_executor=http_executor,
        ),
        settings,
        http_executor,
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
async def test_network_agent_bridge_returns_final_answer_through_public_agent_runtime_boundary(
    monkeypatch,
) -> None:
    captured = _patch_runtime(monkeypatch, _RuntimeBridgeUseCase)
    invoker, settings, http_executor = _invoker()

    result = await invoker.invoke(**_invoke_kwargs())

    assert result.answer == "network final answer"
    assert result.provider == "openai"
    assert result.model == "gpt-test"
    assert result.usage == {"input_tokens": 3, "output_tokens": 5, "total_tokens": 8}
    assert result.session_id is not None
    assert result.trace_id is not None
    assert result.streamed_output is False
    assert captured["settings"] is settings
    assert captured["http_executor"] is http_executor
    assert captured["internal_tool_handlers"] == {}
    assert captured["build_calls"] == 1


@pytest.mark.asyncio
async def test_network_agent_runtime_is_reused_between_invocations(monkeypatch) -> None:
    captured = _patch_runtime(monkeypatch, _RuntimeBridgeUseCase)
    invoker, _settings, _http_executor = _invoker()

    await invoker.invoke(**_invoke_kwargs())
    await invoker.invoke(**_invoke_kwargs())

    assert captured["build_calls"] == 1


@pytest.mark.asyncio
async def test_network_agent_bridge_batches_public_final_tokens(monkeypatch) -> None:
    _patch_runtime(monkeypatch, _StreamingBridgeUseCase)
    invoker, _settings, _http_executor = _invoker()
    events = []

    async def stream_handler(event_type, payload):
        events.append((event_type, payload))

    result = await invoker.invoke(
        **_invoke_kwargs(stream_handler=stream_handler)
    )

    assert result.answer == "network final answer"
    assert result.streamed_output is True
    assert [(event_type, payload["content"]) for event_type, payload in events] == [
        ("token", "network final answer"),
    ]


@pytest.mark.asyncio
async def test_network_internal_delegation_tool_uses_invocation_context(monkeypatch) -> None:
    captured = _patch_runtime(monkeypatch, _DelegationBridgeUseCase)
    invoker, _settings, _http_executor = _invoker()

    async def delegate(arguments):
        assert arguments == {"task": "resolve specialist task"}
        return {"success": True, "result": "specialist result"}

    internal_tool = InternalDelegationTool(
        id=_DELEGATION_TOOL_ID,
        name="delegate_specialist",
        description="Delegate to specialist",
        handler=delegate,
    )

    result = await invoker.invoke(
        **_invoke_kwargs(internal_tools=[internal_tool])
    )

    assert result.answer == "root integrated specialist result"
    assert captured["internal_tool_handlers"] == {}
    assert captured["build_calls"] == 1
