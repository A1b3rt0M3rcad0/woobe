"""Tests for metering dispatcher and idempotent usage projections."""

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from modules.metering.infra.database.unit_of_work import MeteringUnitOfWork
from modules.metering.infra.messaging.inbox_handlers import (
    HANDLER_MAP,
    MeteringInboxEventRouter,
    handle_execution_completed,
    handle_execution_failed,
    handle_fallback,
    handle_llm_request,
    handle_noop,
    handle_tool_execution,
)
from modules.metering.infra.workers.inbox_processor import MeteringInboxProcessorWorker
from shared.workers.inbox_processor_base import InboxProcessingRecord


def _make_model_mock(**kwargs):
    model = MagicMock()
    for key, value in kwargs.items():
        setattr(model, key, value)
    return model


@pytest.fixture
def mock_session():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock())
    return session


@pytest.fixture
def mock_uow(mock_session):
    uow = MagicMock(spec=MeteringUnitOfWork)
    uow.session = mock_session
    return uow


@pytest.fixture
def router():
    return MeteringInboxEventRouter()


@pytest.fixture
def execution_payload():
    return {
        "trace_id": str(uuid4()),
        "project_id": str(uuid4()),
        "agent_id": str(uuid4()),
        "input_tokens": 100,
        "output_tokens": 50,
        "cost_usd": 0.015,
        "cost_status": "known",
        "usage_complete": True,
    }


class TestAtomicEffect:
    @pytest.mark.asyncio
    async def test_requested_handler_is_noop(self, mock_uow, mock_session, execution_payload):
        await handle_noop(
            event_type="agent.execution.requested.v1",
            payload=execution_payload,
            uow=mock_uow,
        )
        assert not mock_session.add.called

    @pytest.mark.asyncio
    async def test_llm_completed_records_one_llm_call(
        self,
        mock_uow,
        mock_session,
        execution_payload,
    ):
        await handle_llm_request(
            event_type="agent.execution.llm_completed.v1",
            payload={**execution_payload, "call_id": str(uuid4())},
            uow=mock_uow,
            source_event_id=uuid4(),
        )
        assert mock_session.add.called
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_tool_execution_records_call(
        self,
        mock_uow,
        mock_session,
        execution_payload,
    ):
        await handle_tool_execution(
            event_type="agent.execution.tool_completed.v1",
            payload={
                **execution_payload,
                "tool_call_id": str(uuid4()),
                "tool_id": str(uuid4()),
                "tool_name": "calculator",
            },
            uow=mock_uow,
            source_event_id=uuid4(),
        )
        assert mock_session.add.called
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_fallback_records_metadata_event(
        self,
        mock_uow,
        mock_session,
        execution_payload,
    ):
        await handle_fallback(
            event_type="agent.execution.fallback_triggered.v1",
            payload=execution_payload,
            uow=mock_uow,
            source_event_id=uuid4(),
        )
        assert mock_session.add.called

    @pytest.mark.asyncio
    async def test_completed_handler_records_runtime_request(
        self,
        mock_uow,
        mock_session,
        execution_payload,
    ):
        await handle_execution_completed(
            event_type="agent.execution.completed.v1",
            payload=execution_payload,
            uow=mock_uow,
            source_event_id=uuid4(),
        )
        assert mock_session.add.called
        assert mock_session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_failed_handler_records_failed_runtime_request(
        self,
        mock_uow,
        mock_session,
        execution_payload,
    ):
        await handle_execution_failed(
            event_type="agent.execution.failed.v1",
            payload=execution_payload,
            uow=mock_uow,
            source_event_id=uuid4(),
        )
        assert mock_session.add.called
        assert mock_session.execute.call_count == 2


class TestRouterDispatch:
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
    async def test_router_dispatches_to_handler(self, router):
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


class TestProcessorIntegration:
    @pytest.mark.asyncio
    async def test_processor_passes_uow_and_source_identity_to_handler(self, mock_uow):
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
        processor._uow = mock_uow
        processor._repo = AsyncMock()
        processor._event_map = {}
        source_event_id = uuid4()
        record = InboxProcessingRecord(
            id=uuid4(),
            outbox_origin_id=str(source_event_id),
            aggregate_type="agent",
            event_type="agent.execution.requested.v1",
            event_version=1,
            payload={"project_id": str(uuid4())},
            correlation_id=uuid4(),
            causation_id=uuid4(),
        )
        await processor.process(record)
        assert call_kwargs.get("uow") is mock_uow
        assert call_kwargs.get("source_event_id") == source_event_id


class TestRegistryRegistration:
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
