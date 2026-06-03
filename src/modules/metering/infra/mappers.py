from datetime import UTC, datetime

from modules.metering.domain.entities import UsageDailyAgent, UsageDailyProject, UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.infra.models import (
    UsageDailyAgentModel,
    UsageDailyProjectModel,
    UsageEventModel,
)


def usage_event_entity_to_model(entity: UsageEvent) -> UsageEventModel:
    return UsageEventModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        event_type=entity.event_type.value if isinstance(entity.event_type, UsageEventType) else entity.event_type,
        quantity=entity.quantity,
        unit=entity.unit.value if isinstance(entity.unit, UsageUnit) else entity.unit,
        cost_usd=entity.cost_usd,
        data=entity.data,
    )


def usage_event_model_to_entity(model: UsageEventModel) -> UsageEvent:
    return UsageEvent(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        event_type=UsageEventType(model.event_type),
        quantity=model.quantity,
        unit=UsageUnit(model.unit),
        cost_usd=model.cost_usd,
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def usage_daily_project_entity_to_model(entity: UsageDailyProject) -> UsageDailyProjectModel:
    return UsageDailyProjectModel(
        project_id=entity.project_id,
        day=entity.day,
        requests=entity.requests,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        embedding_tokens=entity.embedding_tokens,
        tool_calls=entity.tool_calls,
        vector_queries=entity.vector_queries,
        storage_mb=entity.storage_mb,
        cost_usd=entity.cost_usd,
        updated_at=entity.updated_at or datetime.now(UTC),
    )


def usage_daily_project_model_to_entity(model: UsageDailyProjectModel) -> UsageDailyProject:
    return UsageDailyProject(
        project_id=model.project_id,
        day=model.day,
        requests=model.requests,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        embedding_tokens=model.embedding_tokens,
        tool_calls=model.tool_calls,
        vector_queries=model.vector_queries,
        storage_mb=model.storage_mb,
        cost_usd=model.cost_usd,
        updated_at=model.updated_at,
    )


def usage_daily_agent_entity_to_model(entity: UsageDailyAgent) -> UsageDailyAgentModel:
    return UsageDailyAgentModel(
        agent_id=entity.agent_id,
        day=entity.day,
        project_id=entity.project_id,
        requests=entity.requests,
        input_tokens=entity.input_tokens,
        output_tokens=entity.output_tokens,
        tool_calls=entity.tool_calls,
        vector_queries=entity.vector_queries,
        cost_usd=entity.cost_usd,
        updated_at=entity.updated_at or datetime.now(UTC),
    )


def usage_daily_agent_model_to_entity(model: UsageDailyAgentModel) -> UsageDailyAgent:
    return UsageDailyAgent(
        agent_id=model.agent_id,
        day=model.day,
        project_id=model.project_id,
        requests=model.requests,
        input_tokens=model.input_tokens,
        output_tokens=model.output_tokens,
        tool_calls=model.tool_calls,
        vector_queries=model.vector_queries,
        cost_usd=model.cost_usd,
        updated_at=model.updated_at,
    )
