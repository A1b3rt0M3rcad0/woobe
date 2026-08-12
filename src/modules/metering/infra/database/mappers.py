from datetime import UTC, datetime

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.infra.database.models import (
    UsageDailyAgentModel,
    UsageDailyProjectModel,
    UsageEventModel,
)


def usage_event_entity_to_model(entity: UsageEvent) -> UsageEventModel:
    return UsageEventModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        network_id=entity.network_id,
        network_execution_id=entity.network_execution_id,
        network_version_id=entity.network_version_id,
        source_event_id=entity.source_event_id,
        occurred_at=entity.occurred_at,
        trace_id=entity.trace_id,
        call_id=entity.call_id,
        environment=entity.environment,
        agent_release_id=entity.agent_release_id,
        agent_release_version=entity.agent_release_version,
        provider=entity.provider,
        model=entity.model,
        provider_model_id=entity.provider_model_id,
        event_type=entity.event_type.value if isinstance(entity.event_type, UsageEventType) else entity.event_type,
        quantity=entity.quantity,
        unit=entity.unit.value if isinstance(entity.unit, UsageUnit) else entity.unit,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        cost_usd=entity.cost_usd,
        cost_status=entity.cost_status,
        cost_reason=entity.cost_reason,
        usage_complete=entity.usage_complete,
        pricing_snapshot=entity.pricing_snapshot,
        data=entity.data,
    )


def usage_event_model_to_entity(model: UsageEventModel) -> UsageEvent:
    return UsageEvent(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        network_id=model.network_id,
        network_execution_id=model.network_execution_id,
        network_version_id=model.network_version_id,
        source_event_id=model.source_event_id,
        occurred_at=model.occurred_at,
        trace_id=model.trace_id,
        call_id=model.call_id,
        environment=model.environment,
        agent_release_id=model.agent_release_id,
        agent_release_version=model.agent_release_version,
        provider=model.provider,
        model=model.model,
        provider_model_id=model.provider_model_id,
        event_type=UsageEventType(model.event_type),
        quantity=model.quantity,
        unit=UsageUnit(model.unit),
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        cost_usd=model.cost_usd,
        cost_status=model.cost_status,
        cost_reason=model.cost_reason,
        usage_complete=model.usage_complete,
        pricing_snapshot=model.pricing_snapshot,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def usage_daily_project_entity_to_model(entity: UsageDailyProject) -> UsageDailyProjectModel:
    return UsageDailyProjectModel(
        project_id=entity.project_id,
        day=entity.day,
        requests=entity.requests,
        successful_requests=entity.successful_requests,
        failed_requests=entity.failed_requests,
        cancelled_requests=entity.cancelled_requests,
        llm_calls=entity.llm_calls,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        embedding_tokens=entity.embedding_tokens,
        tool_calls=entity.tool_calls,
        vector_queries=entity.vector_queries,
        storage_mb=entity.storage_mb,
        cost_usd=entity.cost_usd,
        priced_requests=entity.priced_requests,
        partial_cost_requests=entity.partial_cost_requests,
        unpriced_requests=entity.unpriced_requests,
        last_event_occurred_at=entity.last_event_occurred_at,
        updated_at=entity.updated_at or datetime.now(UTC),
    )


def usage_daily_project_model_to_entity(model: UsageDailyProjectModel) -> UsageDailyProject:
    return UsageDailyProject(
        project_id=model.project_id,
        day=model.day,
        requests=model.requests,
        successful_requests=model.successful_requests,
        failed_requests=model.failed_requests,
        cancelled_requests=model.cancelled_requests,
        llm_calls=model.llm_calls,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        embedding_tokens=model.embedding_tokens,
        tool_calls=model.tool_calls,
        vector_queries=model.vector_queries,
        storage_mb=model.storage_mb,
        cost_usd=model.cost_usd,
        priced_requests=model.priced_requests,
        partial_cost_requests=model.partial_cost_requests,
        unpriced_requests=model.unpriced_requests,
        last_event_occurred_at=model.last_event_occurred_at,
        updated_at=model.updated_at,
    )


def usage_daily_agent_entity_to_model(entity: UsageDailyAgent) -> UsageDailyAgentModel:
    return UsageDailyAgentModel(
        agent_id=entity.agent_id,
        day=entity.day,
        project_id=entity.project_id,
        requests=entity.requests,
        successful_requests=entity.successful_requests,
        failed_requests=entity.failed_requests,
        cancelled_requests=entity.cancelled_requests,
        llm_calls=entity.llm_calls,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        tool_calls=entity.tool_calls,
        vector_queries=entity.vector_queries,
        cost_usd=entity.cost_usd,
        priced_requests=entity.priced_requests,
        partial_cost_requests=entity.partial_cost_requests,
        unpriced_requests=entity.unpriced_requests,
        last_event_occurred_at=entity.last_event_occurred_at,
        updated_at=entity.updated_at or datetime.now(UTC),
    )


def usage_daily_agent_model_to_entity(model: UsageDailyAgentModel) -> UsageDailyAgent:
    return UsageDailyAgent(
        agent_id=model.agent_id,
        day=model.day,
        project_id=model.project_id,
        requests=model.requests,
        successful_requests=model.successful_requests,
        failed_requests=model.failed_requests,
        cancelled_requests=model.cancelled_requests,
        llm_calls=model.llm_calls,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        tool_calls=model.tool_calls,
        vector_queries=model.vector_queries,
        cost_usd=model.cost_usd,
        priced_requests=model.priced_requests,
        partial_cost_requests=model.partial_cost_requests,
        unpriced_requests=model.unpriced_requests,
        last_event_occurred_at=model.last_event_occurred_at,
        updated_at=model.updated_at,
    )
