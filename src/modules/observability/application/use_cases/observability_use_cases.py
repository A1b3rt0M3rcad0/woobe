import logging
from uuid import UUID

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.domain.repositories import TraceEventRepository, TraceRepository
from modules.observability.application.dtos.observability_dtos import (
    CreateTraceEventInput,
    CreateTraceEventOutput,
    CreateTraceInput,
    CreateTraceOutput,
    ListTracesInput,
    TraceEventResponse,
    TraceListItemResponse,
    TraceSummaryResponse,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.errors import NotFoundError

logger = logging.getLogger(__name__)


class CreateTraceUseCase:

    def __init__(
        self,
        repo: TraceRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: CreateTraceInput) -> CreateTraceOutput:
        trace = Trace(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            session_id=input_dto.session_id,
            external_session_id=input_dto.external_session_id,
            tenant_id=input_dto.tenant_id,
            user_id=input_dto.user_id,
            status=TraceStatus(input_dto.status),
            started_at=input_dto.started_at,
            ended_at=input_dto.ended_at,
            total_latency_ms=input_dto.total_latency_ms,
            total_cost_usd=input_dto.total_cost_usd,
            provider=input_dto.provider,
            model=input_dto.model,
            fallback_used=input_dto.fallback_used,
            error=input_dto.error,
            data=input_dto.data,
        )
        saved = await self._repo.save(trace)

        await self._outbox.write(
            aggregate_type="Trace",
            aggregate_id=saved.id,
            event_type="trace.created.v1",
            payload={
                "project_id": str(saved.project_id),
                "status": saved.status,
                "provider": saved.provider,
            },
            routing_key="trace.created.v1",
            idempotency_key=f"observability:trace.created.v1:{saved.id}",
        )

        return CreateTraceOutput(trace_id=saved.id)


class CreateTraceEventUseCase:

    def __init__(
        self,
        repo: TraceEventRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(
        self, input_dto: CreateTraceEventInput
    ) -> CreateTraceEventOutput:
        event = TraceEvent(
            trace_id=input_dto.trace_id,
            project_id=input_dto.project_id,
            event_type=TraceEventType(input_dto.event_type),
            latency_ms=input_dto.latency_ms,
            cost_usd=input_dto.cost_usd,
            payload=input_dto.payload,
            payload_ref=input_dto.payload_ref,
        )
        saved = await self._repo.save(event)

        await self._outbox.write(
            aggregate_type="TraceEvent",
            aggregate_id=saved.id,
            event_type="trace_event.created.v1",
            payload={
                "trace_id": str(saved.trace_id),
                "event_type": saved.event_type,
            },
            routing_key="trace_event.created.v1",
            idempotency_key=f"observability:trace_event.created.v1:{saved.id}",
        )

        return CreateTraceEventOutput(event_id=saved.id)


class GetTraceUseCase:

    def __init__(
        self,
        trace_repo: TraceRepository,
        event_repo: TraceEventRepository,
    ) -> None:
        self._trace_repo = trace_repo
        self._event_repo = event_repo

    async def execute(self, trace_id: UUID) -> TraceSummaryResponse:
        trace = await self._trace_repo.get_by_id(trace_id)
        if trace is None:
            raise NotFoundError(f"Trace {trace_id} not found")

        events = await self._event_repo.list_by_trace(trace_id)

        logger.info("Trace detail response usage debug", extra={
            "trace_id": str(trace_id),
            "has_data": trace.data is not None,
            "data_keys": list(trace.data) if trace.data else None,
            "usage_unavailable": trace.data is None or trace.data.get("input_tokens") is None,
        })
        return TraceSummaryResponse(
            id=trace.id,
            project_id=trace.project_id,
            agent_id=trace.agent_id,
            session_id=trace.session_id,
            status=trace.status,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            total_latency_ms=trace.total_latency_ms,
            total_cost_usd=trace.total_cost_usd,
            provider=trace.provider,
            model=trace.model,
            error=trace.error,
            data=trace.data,
            created_at=trace.created_at,
            events=[
                TraceEventResponse(
                    id=e.id,
                    event_type=e.event_type,
                    latency_ms=e.latency_ms,
                    cost_usd=e.cost_usd,
                    payload=e.payload,
                    payload_ref=e.payload_ref,
                    created_at=e.created_at,
                )
                for e in events
            ],
        )


class ListTracesUseCase:

    def __init__(self, repo: TraceRepository) -> None:
        self._repo = repo

    async def execute(self, input_dto: ListTracesInput) -> list[TraceListItemResponse]:
        if not input_dto.project_id:
            return []

        if input_dto.session_id:
            traces = await self._repo.list_by_session(
                input_dto.session_id, input_dto.limit, input_dto.offset
            )
        elif input_dto.agent_id:
            traces = await self._repo.list_by_project_and_agent(
                input_dto.project_id, input_dto.agent_id, input_dto.limit, input_dto.offset
            )
        else:
            traces = await self._repo.list_by_project(
                input_dto.project_id, input_dto.limit, input_dto.offset
            )

        return [
            TraceListItemResponse(
                id=t.id,
                project_id=t.project_id,
                agent_id=t.agent_id,
                session_id=t.session_id,
                status=str(t.status.value) if hasattr(t.status, "value") else str(t.status),
                provider=t.provider,
                model=t.model,
                total_latency_ms=t.total_latency_ms,
                total_cost_usd=t.total_cost_usd,
                error=t.error,
                data=t.data,
                started_at=t.started_at,
                ended_at=t.ended_at,
                created_at=t.created_at,
            )
            for t in traces
        ]
