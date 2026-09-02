import logging
from uuid import UUID

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
from modules.observability.application.interfaces.outbox import OutboxEventWriter
from modules.observability.application.interfaces.repositories import (
    TraceEventRepository,
    TraceRepository,
)
from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.domain.errors import TraceNotFoundError

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
            network_id=input_dto.network_id,
            network_execution_id=input_dto.network_execution_id,
            network_session_id=input_dto.network_session_id,
            network_version_id=input_dto.network_version_id,
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
            provider_model_id=input_dto.provider_model_id,
            provider_credential_id=input_dto.provider_credential_id,
            fallback_provider_model_id=input_dto.fallback_provider_model_id,
            fallback_credential_id=input_dto.fallback_credential_id,
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
                "network_id": str(saved.network_id) if saved.network_id else None,
                "network_execution_id": (
                    str(saved.network_execution_id)
                    if saved.network_execution_id
                    else None
                ),
                "network_version_id": (
                    str(saved.network_version_id) if saved.network_version_id else None
                ),
                "status": saved.status,
                "provider": saved.provider,
                "provider_model_id": (
                    str(saved.provider_model_id) if saved.provider_model_id else None
                ),
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
            raise TraceNotFoundError(f"Trace {trace_id} not found")
        events = await self._event_repo.list_by_trace(trace_id)
        logger.info(
            "Trace detail response usage debug",
            extra={
                "trace_id": str(trace_id),
                "has_data": trace.data is not None,
                "data_keys": list(trace.data) if trace.data else None,
                "usage_unavailable": (
                    trace.data is None or trace.data.get("input_tokens") is None
                ),
            },
        )
        return TraceSummaryResponse(
            id=trace.id,
            project_id=trace.project_id,
            agent_id=trace.agent_id,
            session_id=trace.session_id,
            network_id=trace.network_id,
            network_execution_id=trace.network_execution_id,
            network_session_id=trace.network_session_id,
            network_version_id=trace.network_version_id,
            status=trace.status,
            started_at=trace.started_at,
            ended_at=trace.ended_at,
            total_latency_ms=trace.total_latency_ms,
            total_cost_usd=trace.total_cost_usd,
            provider=trace.provider,
            model=trace.model,
            provider_model_id=trace.provider_model_id,
            provider_credential_id=trace.provider_credential_id,
            fallback_provider_model_id=trace.fallback_provider_model_id,
            fallback_credential_id=trace.fallback_credential_id,
            fallback_used=trace.fallback_used,
            error=trace.error,
            data=trace.data,
            created_at=trace.created_at,
            events=[
                TraceEventResponse(
                    id=event.id,
                    event_type=event.event_type,
                    latency_ms=event.latency_ms,
                    cost_usd=event.cost_usd,
                    payload=event.payload,
                    payload_ref=event.payload_ref,
                    created_at=event.created_at,
                )
                for event in events
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
                input_dto.project_id,
                input_dto.agent_id,
                input_dto.limit,
                input_dto.offset,
            )
        elif input_dto.network_id:
            traces = await self._repo.list_by_project_and_network(
                input_dto.project_id,
                input_dto.network_id,
                input_dto.limit,
                input_dto.offset,
            )
        else:
            traces = await self._repo.list_by_project(
                input_dto.project_id, input_dto.limit, input_dto.offset
            )
        return [
            TraceListItemResponse(
                id=trace.id,
                project_id=trace.project_id,
                agent_id=trace.agent_id,
                session_id=trace.session_id,
                network_id=trace.network_id,
                network_execution_id=trace.network_execution_id,
                network_session_id=trace.network_session_id,
                network_version_id=trace.network_version_id,
                status=(
                    str(trace.status.value)
                    if hasattr(trace.status, "value")
                    else str(trace.status)
                ),
                provider=trace.provider,
                model=trace.model,
                provider_model_id=trace.provider_model_id,
                provider_credential_id=trace.provider_credential_id,
                fallback_provider_model_id=trace.fallback_provider_model_id,
                fallback_credential_id=trace.fallback_credential_id,
                fallback_used=trace.fallback_used,
                total_latency_ms=trace.total_latency_ms,
                total_cost_usd=trace.total_cost_usd,
                error=trace.error,
                data=trace.data,
                started_at=trace.started_at,
                ended_at=trace.ended_at,
                created_at=trace.created_at,
            )
            for trace in traces
        ]
