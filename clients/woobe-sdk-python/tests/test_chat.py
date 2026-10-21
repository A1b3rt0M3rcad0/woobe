from __future__ import annotations

from collections.abc import AsyncIterator

import pytest

from woobe import Woobe
from woobe._transport.sse import SseFrame
from woobe.errors import (
    WoobeConnectionError,
    WoobeProtocolError,
    WoobeRecoveryError,
    WoobeRequestError,
)


def _event_frame(
    event_type: str,
    sequence: int,
    payload: dict | None = None,
    *,
    run_kind: str = "AGENT",
) -> SseFrame:
    return SseFrame(
        event=event_type,
        event_id=str(sequence),
        data={
            "protocol_version": 2,
            "event_id": f"evt-{sequence}",
            "run_id": "run-1",
            "session_id": "session-1",
            "run_kind": run_kind,
            "sequence": sequence,
            "type": event_type,
            "occurred_at": "2026-09-16T20:30:00Z",
            "payload": payload or {},
        },
    )


class _FakeTransport:
    def __init__(
        self,
        *,
        disconnect_once: bool = False,
        fail_before_identity: bool = False,
        include_heartbeat: bool = False,
    ) -> None:
        self.disconnect_once = disconnect_once
        self.fail_before_identity = fail_before_identity
        self.include_heartbeat = include_heartbeat
        self.calls: list[str] = []
        self.idempotency_keys: list[str] = []
        self.external_contexts: list[dict | None] = []

    async def aclose(self) -> None:
        return None

    async def resolve_active_run(self, *, key: str, session_id: str) -> str | None:
        del key, session_id
        self.calls.append("active")
        return None

    async def stream_new_run(
        self,
        *,
        key: str,
        message: str,
        session_id: str | None,
        external_context: dict | None,
        idempotency_key: str,
    ) -> AsyncIterator[SseFrame]:
        del key, message, session_id
        self.calls.append("new")
        self.idempotency_keys.append(idempotency_key)
        self.external_contexts.append(external_context)

        if self.fail_before_identity:
            raise WoobeConnectionError("connection lost")

        if self.include_heartbeat:
            yield SseFrame(
                event="heartbeat",
                data={
                    "protocol_version": 2,
                    "type": "heartbeat",
                    "occurred_at": "2026-09-16T20:30:00Z",
                },
            )

        yield _event_frame("meta", 1, {"trace_id": "trace-1"})
        yield _event_frame("token", 2, {"content": "Olá"})

        if self.disconnect_once:
            self.disconnect_once = False
            raise WoobeConnectionError("connection lost")

        yield _event_frame("done", 3, {"answer": "Olá"})

    async def stream_run(self, *, key: str, run_id: str) -> AsyncIterator[SseFrame]:
        del key
        assert run_id == "run-1"
        self.calls.append("reattach")
        yield _event_frame(
            "run.state",
            2,
            {"status": "running", "output": "Olá"},
        )
        yield _event_frame("done", 3, {"answer": "Olá!"})


@pytest.mark.asyncio
async def test_events_start_request_and_yield_only_semantic_woobe_events() -> None:
    transport = _FakeTransport(include_heartbeat=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")
    chat = agent.chat(input="Olá")

    assert transport.calls == []

    events = [event async for event in chat.events()]

    assert transport.calls == ["new"]
    assert [event.type for event in events] == ["meta", "token", "done"]
    assert all(event.run_id == "run-1" for event in events)
    assert all(event.session_id == "session-1" for event in events)
    assert all(event.run_kind == "AGENT" for event in events)
    assert chat.run_id == "run-1"
    assert chat.session_id == "session-1"


@pytest.mark.asyncio
async def test_chat_exposes_typed_terminal_result() -> None:
    class ResultTransport(_FakeTransport):
        async def stream_new_run(self, **kwargs) -> AsyncIterator[SseFrame]:
            del kwargs
            self.calls.append("new")
            yield _event_frame("meta", 1, {"trace_id": "trace-1"})
            yield _event_frame(
                "done",
                2,
                {
                    "answer": "Olá Alberto",
                    "message_id": "message-1",
                    "trace_id": "trace-1",
                    "usage": {
                        "input_tokens": 10,
                        "output_tokens": 20,
                        "total_tokens": 30,
                        "cost_usd": 0.001,
                    },
                    "sources": [
                        {
                            "document_title": "Manual",
                            "document_id": "doc-1",
                            "score": 0.9,
                        }
                    ],
                    "tool_calls": [
                        {
                            "tool_call_id": "tool-call-1",
                            "tool_name": "lookup_customer",
                            "success": True,
                            "duration_ms": 12,
                        }
                    ],
                    "model": "deepseek-v4-flash",
                    "provider": "custom",
                    "provider_model_id": "provider-model-1",
                    "provider_credential_id": "credential-1",
                    "fallback_used": False,
                    "latency_ms": 1234,
                    "parsed_output": {"message": "Olá Alberto"},
                    "output_parse_error": None,
                    "execution_events": [],
                    "diagnostics": {
                        "schema_version": 5,
                        "agent_runtime_latency_ms": 1200,
                        "llm_call_count": 1,
                        "tool_call_count": 1,
                        "usage_complete": True,
                        "cost_status": "known",
                        "execution_context": "production",
                        "execution_strategy": "standard",
                        "agent_release_id": "release-1",
                        "agent_release_version": "v1.2.3",
                        "fallback_used": False,
                    },
                },
            )

    transport = ResultTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")
    chat = agent.chat(input="Olá")

    assert chat.result is None

    events = [event async for event in chat.events()]

    assert [event.type for event in events] == ["meta", "done"]
    assert chat.result is not None
    assert chat.result.answer == "Olá Alberto"
    assert chat.result.run_id == "run-1"
    assert chat.result.session_id == "session-1"
    assert chat.result.message_id == "message-1"
    assert chat.result.usage is not None
    assert chat.result.usage.total_tokens == 30
    assert chat.result.usage.cost_usd == 0.001
    assert chat.result.sources[0].document_title == "Manual"
    assert chat.result.tool_calls[0].tool_name == "lookup_customer"
    assert chat.result.model == "deepseek-v4-flash"
    assert chat.result.provider == "custom"
    assert chat.result.parsed_output == {"message": "Olá Alberto"}
    assert chat.result.diagnostics is not None
    assert chat.result.diagnostics.agent_release_id == "release-1"
    assert chat.result.diagnostics.agent_release_version == "v1.2.3"
    assert chat.result.diagnostics.execution_strategy == "standard"
    assert chat.result.agent_release_id == "release-1"
    assert chat.result.agent_release_version == "v1.2.3"
    assert chat.result.execution_context == "production"
    assert chat.result.execution_strategy == "standard"


@pytest.mark.asyncio
async def test_network_completed_output_is_normalized_to_answer() -> None:
    class NetworkResultTransport(_FakeTransport):
        async def stream_new_run(self, **kwargs) -> AsyncIterator[SseFrame]:
            del kwargs
            self.calls.append("new")
            yield _event_frame(
                "execution_completed",
                1,
                {
                    "output": "Network answer",
                    "trace_id": "trace-network",
                    "parsed_output": {"answer": "Network answer"},
                },
                run_kind="NETWORK",
            )

    transport = NetworkResultTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    network = woobe.connect.network(alias="network", key="runtime-key")
    chat = network.chat(input="Olá")

    _ = [event async for event in chat.events()]

    assert chat.result is not None
    assert chat.result.answer == "Network answer"
    assert chat.result.run_kind == "NETWORK"
    assert chat.result.terminal_event_type == "execution_completed"
    assert chat.result.parsed_output == {"answer": "Network answer"}


@pytest.mark.asyncio
async def test_terminal_stream_is_closed_before_chat_finishes() -> None:
    class ClosingTransport(_FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.closed = False

        async def stream_new_run(self, **kwargs) -> AsyncIterator[SseFrame]:
            del kwargs
            try:
                yield _event_frame("done", 1, {"answer": "ok"})
            finally:
                self.closed = True

    transport = ClosingTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")
    chat = agent.chat(input="Olá")

    _ = [event async for event in chat.events()]

    assert transport.closed is True
    assert chat.result is not None
    assert chat.result.answer == "ok"


@pytest.mark.asyncio
async def test_external_context_is_forwarded_only_on_initial_run_request() -> None:
    transport = _FakeTransport(disconnect_once=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    external_context = {
        "customer_id": "customer-123",
        "language": "pt-BR",
    }
    events = [
        event
        async for event in agent.chat(
            input="Olá",
            external_context=external_context,
        ).events()
    ]

    assert [event.type for event in events] == ["meta", "token", "run.state", "done"]
    assert transport.calls == ["new", "reattach"]
    assert transport.external_contexts == [external_context]


@pytest.mark.asyncio
async def test_transport_disconnect_reattaches_same_run_without_second_post() -> None:
    transport = _FakeTransport(disconnect_once=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    events = [event async for event in agent.chat(input="Olá").events()]

    assert transport.calls == ["new", "reattach"]
    assert [event.type for event in events] == ["meta", "token", "run.state", "done"]


@pytest.mark.asyncio
async def test_agent_initial_failure_fails_closed_instead_of_reposting() -> None:
    transport = _FakeTransport(fail_before_identity=True)
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    with pytest.raises(WoobeRecoveryError):
        _ = [event async for event in agent.chat(input="Olá").events()]

    assert transport.calls == ["new"]


@pytest.mark.asyncio
async def test_run_kind_mismatch_is_a_protocol_error() -> None:
    class WrongKindTransport(_FakeTransport):
        async def stream_new_run(self, **kwargs) -> AsyncIterator[SseFrame]:
            del kwargs
            self.calls.append("new")
            yield _event_frame("done", 1, run_kind="NETWORK")

    transport = WrongKindTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    with pytest.raises(WoobeProtocolError):
        _ = [event async for event in agent.chat(input="Olá").events()]


@pytest.mark.asyncio
async def test_pre_acceptance_error_control_frame_is_not_exposed_as_an_event() -> None:
    class ErrorTransport(_FakeTransport):
        async def stream_new_run(self, **kwargs) -> AsyncIterator[SseFrame]:
            del kwargs
            self.calls.append("new")
            yield SseFrame(
                event="error",
                data={
                    "protocol_version": 2,
                    "type": "error",
                    "occurred_at": "2026-09-16T20:30:00Z",
                    "payload": {"message": "runtime disabled", "status_code": 409},
                },
            )

    transport = ErrorTransport()
    woobe = Woobe(base_url="http://unused", reconnect_base_delay_seconds=0)
    woobe._transport = transport
    agent = woobe.connect.agent(alias="support", key="runtime-key")

    with pytest.raises(WoobeRequestError, match="runtime disabled"):
        _ = [event async for event in agent.chat(input="Olá").events()]
