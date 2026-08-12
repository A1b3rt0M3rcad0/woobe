from typing import Any
from uuid import UUID

from modules.observability.domain.entities import Trace, TraceEvent
from modules.observability.domain.enums import TraceEventType, TraceStatus
from modules.observability.infra.database.models import TraceEventModel, TraceModel


def _uuid(value: Any) -> UUID | None:
    if value in (None, ""):
        return None
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return None


def trace_entity_to_model(entity: Trace) -> TraceModel:
    data = entity.data or {}
    return TraceModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        session_id=entity.session_id,
        network_id=entity.network_id or _uuid(data.get("network_id")),
        network_execution_id=entity.network_execution_id
        or _uuid(data.get("network_execution_id")),
        network_session_id=entity.network_session_id
        or _uuid(data.get("network_session_id")),
        network_version_id=entity.network_version_id
        or _uuid(data.get("network_version_id")),
        external_session_id=entity.external_session_id,
        tenant_id=entity.tenant_id,
        user_id=entity.user_id,
        status=entity.status.value if isinstance(entity.status, TraceStatus) else entity.status,
        started_at=entity.started_at,
        ended_at=entity.ended_at,
        total_latency_ms=entity.total_latency_ms,
        total_cost_usd=entity.total_cost_usd,
        provider=entity.provider,
        model=entity.model,
        provider_model_id=entity.provider_model_id,
        provider_credential_id=entity.provider_credential_id,
        fallback_provider_model_id=entity.fallback_provider_model_id,
        fallback_credential_id=entity.fallback_credential_id,
        fallback_used=entity.fallback_used,
        error=entity.error,
        data=entity.data,
    )


def trace_model_to_entity(model: TraceModel) -> Trace:
    return Trace(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        session_id=model.session_id,
        network_id=model.network_id,
        network_execution_id=model.network_execution_id,
        network_session_id=model.network_session_id,
        network_version_id=model.network_version_id,
        external_session_id=model.external_session_id,
        tenant_id=model.tenant_id,
        user_id=model.user_id,
        status=TraceStatus(model.status),
        started_at=model.started_at,
        ended_at=model.ended_at,
        total_latency_ms=model.total_latency_ms,
        total_cost_usd=model.total_cost_usd,
        provider=model.provider,
        model=model.model,
        provider_model_id=model.provider_model_id,
        provider_credential_id=model.provider_credential_id,
        fallback_provider_model_id=model.fallback_provider_model_id,
        fallback_credential_id=model.fallback_credential_id,
        fallback_used=model.fallback_used,
        error=model.error,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def trace_event_entity_to_model(entity: TraceEvent) -> TraceEventModel:
    return TraceEventModel(
        id=entity.id,
        trace_id=entity.trace_id,
        project_id=entity.project_id,
        event_type=entity.event_type.value if isinstance(entity.event_type, TraceEventType) else entity.event_type,
        latency_ms=entity.latency_ms,
        cost_usd=entity.cost_usd,
        payload=entity.payload,
        payload_ref=entity.payload_ref,
    )


def trace_event_model_to_entity(model: TraceEventModel) -> TraceEvent:
    return TraceEvent(
        id=model.id,
        trace_id=model.trace_id,
        project_id=model.project_id,
        event_type=TraceEventType(model.event_type),
        latency_ms=model.latency_ms,
        cost_usd=model.cost_usd,
        payload=model.payload,
        payload_ref=model.payload_ref,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
