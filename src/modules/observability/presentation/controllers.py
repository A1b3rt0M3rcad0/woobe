from uuid import UUID

from fastapi import APIRouter, Depends

from modules.observability.application.providers import ObservabilityProviders
from modules.observability.presentation.schemas import (
    CreateTraceEventRequest,
    CreateTraceRequest,
    TraceDetailResponse,
    TraceEventResponse,
    TraceResponse,
)
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/observability", tags=["observability"])


@router.post("/traces", status_code=201)
async def create_trace(
    body: CreateTraceRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = ObservabilityProviders(manager.session)
    result = await providers.create_trace_use_case().execute(body)
    return created({"trace_id": str(result.trace_id)})


@router.post("/traces/{trace_id}/events", status_code=201)
async def add_trace_event(
    trace_id: UUID,
    body: CreateTraceEventRequest,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = ObservabilityProviders(manager.session)
    result = await providers.create_trace_event_use_case().execute(body)
    return created({"event_id": str(result.event_id)})


@router.get("/traces/{trace_id}")
async def get_trace(
    trace_id: UUID,
    manager: SessionManager = Depends(get_session_manager),
):
    providers = ObservabilityProviders(manager.session)
    trace = await providers.get_trace_use_case().execute(trace_id)
    return ok(
        TraceDetailResponse(
            trace=TraceResponse(
                id=trace.id,
                status=str(trace.status),
                provider=trace.provider,
                model=trace.model,
                total_latency_ms=trace.total_latency_ms,
                total_cost_usd=trace.total_cost_usd,
                error=trace.error,
                created_at=trace.created_at,
            ),
            events=[
                TraceEventResponse(
                    id=e.id,
                    event_type=str(e.event_type),
                    latency_ms=e.latency_ms,
                    cost_usd=e.cost_usd,
                    payload=e.payload,
                    created_at=e.created_at,
                )
                for e in trace.events
            ],
        )
    )
