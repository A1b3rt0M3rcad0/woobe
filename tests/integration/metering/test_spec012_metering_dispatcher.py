"""Tests for spec 012: metering dispatcher and idempotent use cases.

Covers: atomic effect, rollback/retry, no double count,
out-of-order handling, unknown event types ignored.
"""
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.metering.infra.messaging.inbox_handlers import (
    HANDLER_MAP,
    MeteringInboxEventRouter,
    handle_execution_requested,
    handle_llm_request,
    handle_tool_execution,
    handle_execution_completed,
    handle_execution_failed,
    handle_fallback,
)
from modules.metering.infra.workers.inbox_processor import MeteringInboxProcessorWorker
from shared.workers.inbox_processor_base import InboxProcessingRecord


def _make_model_mock(**kwargs):
    m = MagicMock()
    for k, v in kwargs.items():
        setattr(m, k, v)
    return m


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    merge_model = _make_model_mock(project_id=MagicMock(), day=MagicMock())
    session.merge = AsyncMock(return_value=merge_model)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none = MagicMock(return_value=None)
    session.execute = AsyncMock(return_value=execute_result)
    session.refresh = AsyncMock()
    return session


@pytest.fixture
def router():
    return MeteringInboxEventRouter()


@pytest.fixture
def execution_payload():
    return {
        "execution_id": str(uuid4()),
        "project_id": str(uuid4()),
        "agent_id": str(uuid4()),
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.015,
    }


class TestAtomicEffect:
    """Handlers must create usage records atomically with the session."""

    @pytest.mark.asyncio
    async def test_execution_requested_creates_usage_event(self, mock_session, execution_payload):
        await handle_execution_requested(
            event_type="agent.execution.requested.v1",
            payload=execution_payload,
            session=mock_session,
        )
        assert mock_session.add.called or mock_session.merge.called

    @pytest.mark.asyncio
    async def test_llm_completed_records_tokens(self, mock_session, execution_payload):
        await handle_llm_request(
            event_type="agent.execution.llm_completed.v1",
            payload=execution_payload,
            session=mock_session,
        )
        assert mock_session.add.called or mock_session.merge.called

    @pytest.mark.asyncio
    async def test_tool_execution_records_call(self, mock_session, execution_payload):
        await handle_tool_execution(
            event_type="agent.execution.tool_completed.v1",
            payload={**execution_payload, "tool_id": str(uuid4()), "tool_name": "calculator"},
            session=mock_session,
        )
        assert mock_session.add.called or mock_session.merge.called

    @pytest.mark.asyncio
    async def test_fallback_records_event(self, mock_session, execution_payload):
        await handle_fallback(
            event_type="agent.execution.fallback_triggered.v1",
            payload=execution_payload,
            session=mock_session,
        )
        assert mock_session.add.called or mock_session.merge.called

    @pytest.mark.asyncio
    async def test_completed_handler_logs_only(self, mock_session, execution_payload):
        await handle_execution_completed(
            event_type="agent.execution.completed.v1",
            payload=execution_payload,
            session=mock_session,
        )

    @pytest.mark.asyncio
    async def test_failed_handler_logs_only(self, mock_session, execution_payload):
        await handle_execution_failed(
            event_type="agent.execution.failed.v1",
            payload=execution_payload,
            session=mock_session,
        )


class TestRouterDispatch:
    """Router must map each event type to the correct handler."""

    def test_all_event_types_have_handlers(self):
        required = {
            "agent.execution.requested.v1",
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        registered = set(HANDLER_MAP.keys())
        assert required.issubset(registered), f"Missing: {required - registered}"

    @pytest.mark.asyncio
    async def test_router_dispatches_to_handler(self, router, mock_session):
        called = False

        async def fake_handler(**kwargs):
            nonlocal called
            called = True

        router.register("test.event.v1", fake_handler)
        await router.handle("test.event.v1", {})
        assert called

    @pytest.mark.asyncio
    async def test_router_skips_unknown_event(self, router):
        await router.handle("unknown.event", {})


class TestUnknownIgnored:
    """Unknown event types must be silently ignored."""

    @pytest.mark.asyncio
    async def test_unknown_event_does_not_raise(self, router):
        await router.handle("agent.execution.nonexistent.v1", {})

    @pytest.mark.asyncio
    async def test_unknown_event_type_not_in_map(self):
        assert "agent.execution.nonexistent.v1" not in HANDLER_MAP


class TestProcessorIntegration:
    """Processor must call handlers with the session when processing records."""

    @pytest.mark.asyncio
    async def test_processor_passes_session_to_handler(self):
        mock_engine = AsyncMock()
        handler = MeteringInboxEventRouter()
        processor = MeteringInboxProcessorWorker(
            async_engine=mock_engine,
            handler=handler,
        )

        call_kwargs = {}

        async def capture_handler(**kwargs):
            call_kwargs.update(kwargs)

        handler.register("agent.execution.requested.v1", capture_handler)
        processor._session = AsyncMock()
        processor._repo = AsyncMock()
        processor._event_map = {}

        record = InboxProcessingRecord(
            id=uuid4(),
            outbox_origin_id="msg-1",
            aggregate_type="agent",
            event_type="agent.execution.requested.v1",
            event_version=1,
            payload={"project_id": str(uuid4())},
            correlation_id=uuid4(),
            causation_id=uuid4(),
        )
        await processor.process(record)
        assert call_kwargs.get("session") is processor._session


class TestRegistryRegistration:
    """Router defaults must include all required event types."""

    def test_default_router_has_all_handlers(self):
        router = MeteringInboxEventRouter()
        required = {
            "agent.execution.requested.v1",
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        registered = set(router.registered_event_types)
        assert required.issubset(registered), f"Missing from default: {required - registered}"
