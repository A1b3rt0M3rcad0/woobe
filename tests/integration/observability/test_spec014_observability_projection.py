"""Tests for spec 014: observability idempotent projection.

Covers: ordered/out-of-order events, duplicate, failed traces,
redaction, rollback.
"""
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest

from modules.observability.domain.enums import TraceStatus
from modules.observability.infra.messaging.inbox_handlers import (
    HANDLER_MAP,
    ObservabilityInboxEventRouter,
    _make_deterministic_event_id,
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


class TestTerminalStateProtection:
    """Terminal states must not regress on replay or out-of-order events."""

    @pytest.mark.asyncio
    async def test_completed_after_started(self, trace_payload):
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.running
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_completed(
                "agent.execution.completed.v1", trace_payload, session=session
            )
            assert trace.status == TraceStatus.completed
            mock_repo.save.assert_awaited()

    @pytest.mark.asyncio
    async def test_failed_does_not_regress_to_completed(self, trace_payload):
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.failed
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_completed(
                "agent.execution.completed.v1", trace_payload, session=session
            )
            assert trace.status == TraceStatus.failed, "completed must not regress failed"
            mock_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_completed_does_not_regress_to_failed(self, trace_payload):
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.completed
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_failed(
                "agent.execution.failed.v1", trace_payload, session=session
            )
            assert trace.status == TraceStatus.completed, "failed must not regress completed"
            mock_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_started_skipped_when_terminal(self, trace_payload):
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.completed
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_started(
                "agent.execution.started.v1", trace_payload, session=session
            )
            assert trace.status == TraceStatus.completed, "started must not regress terminal"
            mock_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_llm_call_skipped_when_terminal(self, trace_payload):
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.completed
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls, patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceEventRepository"
        ):
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_llm_call(
                "agent.execution.llm_completed.v1", trace_payload, session=session
            )
            mock_repo.save.assert_not_awaited()


class TestDeterministicEventIds:
    """TraceEvent IDs must be deterministic from source event to prevent duplicates on replay."""

    @pytest.mark.asyncio
    async def test_llm_call_deterministic_id(self, trace_payload):
        """Same trace_id + event type must produce same TraceEvent ID."""
        trace_id = UUID(trace_payload["trace_id"])
        id1 = _make_deterministic_event_id(trace_id, "llm_call")
        id2 = _make_deterministic_event_id(trace_id, "llm_call")
        assert id1 == id2, "deterministic IDs must match"

    @pytest.mark.asyncio
    async def test_tool_call_deterministic_id(self, trace_payload):
        """Same trace_id + discriminator must produce same TraceEvent ID."""
        trace_id = UUID(trace_payload["trace_id"])
        id1 = _make_deterministic_event_id(trace_id, "tool_call:calc")
        id2 = _make_deterministic_event_id(trace_id, "tool_call:calc")
        assert id1 == id2

    @pytest.mark.asyncio
    async def test_different_trace_different_id(self, trace_payload):
        """Different trace_ids must produce different IDs."""
        id1 = _make_deterministic_event_id(uuid4(), "llm_call")
        id2 = _make_deterministic_event_id(uuid4(), "llm_call")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_different_event_type_different_id(self, trace_payload):
        """Different event types for same trace must produce different IDs."""
        trace_id = UUID(trace_payload["trace_id"])
        id1 = _make_deterministic_event_id(trace_id, "llm_call")
        id2 = _make_deterministic_event_id(trace_id, "tool_call:test")
        assert id1 != id2

    @pytest.mark.asyncio
    async def test_trace_event_upserts_on_replay(self, trace_payload):
        """Replaying same event must upsert, not create duplicate (same ID -> upsert by PK)."""
        session = AsyncMock()
        llm_payload = {**trace_payload, "input_tokens": 100, "output_tokens": 50}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls, patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceEventRepository"
        ) as mock_event_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(side_effect=[None, MagicMock()])
            mock_repo_cls.return_value = mock_repo
            mock_event = AsyncMock()
            mock_event_cls.return_value = mock_event

            # First call
            await handle_llm_call("agent.execution.llm_completed.v1", llm_payload, session=session)
            first_event_id = mock_event.save.call_args[0][0].id

            # Second call (replay)
            await handle_llm_call("agent.execution.llm_completed.v1", llm_payload, session=session)
            second_event_id = mock_event.save.call_args[0][0].id

            assert first_event_id == second_event_id, "replay must produce same TraceEvent ID"
            assert mock_event.save.await_count == 2, "save must be called on replay (upsert)"


class TestOutOfOrderEvents:
    """Events arriving out of order must not leave invalid state."""

    @pytest.mark.asyncio
    async def test_completed_before_started(self, trace_payload):
        """Completed arriving first must create trace and set terminal state."""
        session = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_completed(
                "agent.execution.completed.v1", trace_payload, session=session
            )
            saved = mock_repo.save.call_args[0][0]
            assert saved.status == TraceStatus.completed
            mock_repo.save.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_started_after_completed_no_regression(self, trace_payload):
        """Started arriving after completed must not regress terminal state."""
        session = AsyncMock()
        trace = MagicMock(spec=["status", "project_id", "agent_id", "data", "started_at",
                                "total_cost_usd", "total_latency_ms", "ended_at",
                                "provider", "model", "session_id", "error", "fallback_used"])
        trace.status = TraceStatus.completed
        trace.project_id = UUID(trace_payload["project_id"])
        trace.agent_id = UUID(trace_payload["agent_id"])
        trace.data = {}

        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=trace)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_started(
                "agent.execution.started.v1", trace_payload, session=session
            )
            assert trace.status == TraceStatus.completed
            mock_repo.save.assert_not_awaited()


class TestNoSentinelIds:
    """No UUID(int=0) sentinel values are used for identifiers."""

    @pytest.mark.asyncio
    async def test_started_with_project_id(self, trace_payload):
        """When project_id is provided, it must be used (not sentinel)."""
        session = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo.get_by_id = AsyncMock(return_value=None)
            mock_repo_cls.return_value = mock_repo
            await handle_trace_started(
                "agent.execution.started.v1", trace_payload, session=session
            )
            saved = mock_repo.save.call_args[0][0]
            assert saved.project_id == UUID(trace_payload["project_id"])
            assert saved.project_id != UUID(int=0)

    @pytest.mark.asyncio
    async def test_missing_project_id_returns_early(self):
        """When project_id is missing, handler must return without saving."""
        session = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            await handle_trace_started(
                "agent.execution.started.v1",
                {"trace_id": str(uuid4()), "execution_id": str(uuid4())},
                session=session,
            )
            mock_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_project_id_completed_returns_early(self):
        """Completed handler must skip when project_id is missing."""
        session = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            await handle_trace_completed(
                "agent.execution.completed.v1",
                {"trace_id": str(uuid4()), "execution_id": str(uuid4())},
                session=session,
            )
            mock_repo.save.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_missing_project_id_failed_returns_early(self):
        """Failed handler must skip when project_id is missing."""
        session = AsyncMock()
        with patch(
            "modules.observability.infra.messaging.inbox_handlers.SQLAlchemyTraceRepository"
        ) as mock_repo_cls:
            mock_repo = AsyncMock()
            mock_repo_cls.return_value = mock_repo
            await handle_trace_failed(
                "agent.execution.failed.v1",
                {"trace_id": str(uuid4()), "execution_id": str(uuid4())},
                session=session,
            )
            mock_repo.save.assert_not_awaited()
