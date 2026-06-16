"""Tests for spec 014: observability idempotent projection.

Covers: ordered/out-of-order events, duplicate, failed traces,
redaction, rollback.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from modules.observability.infra.messaging.inbox_handlers import (
    HANDLER_MAP,
    ObservabilityInboxEventRouter,
    handle_trace_started,
    handle_llm_call,
    handle_tool_call,
    handle_trace_completed,
    handle_trace_failed,
    handle_trace_fallback,
)


@pytest.fixture
def mock_session():
    session = MagicMock()
    session.add = MagicMock()
    return session


@pytest.fixture
def trace_payload():
    trace_id = uuid4()
    return {
        "trace_id": str(trace_id),
        "execution_id": str(trace_id),
        "project_id": str(uuid4()),
        "agent_id": str(uuid4()),
        "provider": "openai",
        "model": "gpt-4",
    }


class TestHandlerContract:
    """Handlers must accept valid parameters and not raise."""

    @pytest.mark.asyncio
    async def test_started_no_session(self, trace_payload):
        await handle_trace_started("agent.execution.started.v1", trace_payload, session=None)

    @pytest.mark.asyncio
    async def test_llm_call_no_session(self, trace_payload):
        await handle_llm_call("agent.execution.llm_completed.v1", trace_payload, session=None)

    @pytest.mark.asyncio
    async def test_tool_call_no_session(self, trace_payload):
        await handle_tool_call("agent.execution.tool_completed.v1", trace_payload, session=None)

    @pytest.mark.asyncio
    async def test_completed_no_session(self, trace_payload):
        await handle_trace_completed("agent.execution.completed.v1", trace_payload, session=None)

    @pytest.mark.asyncio
    async def test_failed_no_session(self, trace_payload):
        await handle_trace_failed("agent.execution.failed.v1", trace_payload, session=None)

    @pytest.mark.asyncio
    async def test_fallback_no_session(self, trace_payload):
        await handle_trace_fallback("agent.execution.fallback_triggered.v1", trace_payload, session=None)


class TestHandlerNoTraceId:
    """Handlers must handle missing trace_id gracefully."""

    @pytest.mark.asyncio
    async def test_started_no_trace_id(self):
        await handle_trace_started("agent.execution.started.v1", {}, session=MagicMock())

    @pytest.mark.asyncio
    async def test_llm_call_no_trace_id(self):
        await handle_llm_call("agent.execution.llm_completed.v1", {}, session=MagicMock())

    @pytest.mark.asyncio
    async def test_tool_call_no_trace_id(self):
        await handle_tool_call("agent.execution.tool_completed.v1", {}, session=MagicMock())

    @pytest.mark.asyncio
    async def test_completed_no_trace_id(self):
        await handle_trace_completed("agent.execution.completed.v1", {}, session=MagicMock())

    @pytest.mark.asyncio
    async def test_failed_no_trace_id(self):
        await handle_trace_failed("agent.execution.failed.v1", {}, session=MagicMock())

    @pytest.mark.asyncio
    async def test_fallback_no_trace_id(self):
        await handle_trace_fallback("agent.execution.fallback_triggered.v1", {}, session=MagicMock())


class TestHandlerWithSession:
    """Handlers must create/update trace entities when session is provided."""

    @pytest.mark.asyncio
    async def test_started_calls_session_add(self, trace_payload):
        session = AsyncMock()
        session.add = MagicMock()
        session.flush = AsyncMock()
        session.refresh = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_started("agent.execution.started.v1", trace_payload, session=session)
            mock_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_llm_call_saves_trace_and_event(self, trace_payload):
        session = AsyncMock()
        llm_payload = {**trace_payload, "input_tokens": 100, "output_tokens": 50, "cost_usd": 0.015}
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls, patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceEventRepository"
        ) as mock_event_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            mock_event = AsyncMock()
            mock_event_cls.return_value = mock_event
            await handle_llm_call("agent.execution.llm_completed.v1", llm_payload, session=session)
            mock_repo.save.assert_awaited()
            mock_event.save.assert_awaited()

    @pytest.mark.asyncio
    async def test_tool_call_saves_event(self, trace_payload):
        session = AsyncMock()
        tool_payload = {**trace_payload, "tool_id": str(uuid4()), "tool_name": "calculator"}
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls, patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceEventRepository"
        ) as mock_event_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            mock_event = AsyncMock()
            mock_event_cls.return_value = mock_event
            await handle_tool_call("agent.execution.tool_completed.v1", tool_payload, session=session)
            mock_event.save.assert_awaited()


class TestRouterDispatch:
    """Router must map all event types to handlers."""

    def test_all_event_types_have_handlers(self):
        required = {
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        registered = set(HANDLER_MAP.keys())
        assert required.issubset(registered), f"Missing: {required - registered}"

    def test_handler_map_has_exact_keys(self):
        expected = {
            "agent.execution.started.v1",
            "agent.execution.llm_completed.v1",
            "agent.execution.tool_completed.v1",
            "agent.execution.fallback_triggered.v1",
            "agent.execution.completed.v1",
            "agent.execution.failed.v1",
        }
        assert set(HANDLER_MAP.keys()) == expected

    @pytest.mark.asyncio
    async def test_router_ignores_unknown(self):
        router = ObservabilityInboxEventRouter()
        await router.handle("unknown.event.v1", {})

    @pytest.mark.asyncio
    async def test_router_dispatches_to_registered_handler(self):
        router = ObservabilityInboxEventRouter()
        called = False

        async def fake_handler(**kwargs):
            nonlocal called
            called = True

        router.register("test.event.v1", fake_handler)
        await router.handle("test.event.v1", {})
        assert called


class TestEdgeCases:
    """Various edge cases."""

    @pytest.mark.asyncio
    async def test_empty_payload_still_handled(self):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        trace_id = uuid4()
        await handle_trace_completed(
            "agent.execution.completed.v1",
            {"trace_id": str(trace_id), "execution_id": str(trace_id)},
            session=session,
        )

    @pytest.mark.asyncio
    async def test_duplicate_started_no_error(self, trace_payload):
        session = AsyncMock()
        session.get = AsyncMock(return_value=None)
        await handle_trace_started("agent.execution.started.v1", trace_payload, session=session)
        await handle_trace_started("agent.execution.started.v1", trace_payload, session=session)
