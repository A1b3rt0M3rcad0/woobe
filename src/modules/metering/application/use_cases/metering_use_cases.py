from uuid import UUID

from modules.metering.domain.entities import UsageEvent
from modules.metering.domain.enums import UsageEventType, UsageUnit
from modules.metering.domain.repositories import (
    UsageDailyAgentRepository,
    UsageDailyProjectRepository,
    UsageEventRepository,
)
from modules.metering.application.dtos.metering_dtos import (
    DailyUsageResponse,
    RecordUsageInput,
    RecordUsageOutput,
)
from shared.messaging.outbox_writer import OutboxEventWriter


class RecordUsageUseCase:

    def __init__(
        self,
        repo: UsageEventRepository,
        outbox: OutboxEventWriter,
    ) -> None:
        self._repo = repo
        self._outbox = outbox

    async def execute(self, input_dto: RecordUsageInput) -> RecordUsageOutput:
        event = UsageEvent(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            event_type=UsageEventType(input_dto.event_type),
            quantity=input_dto.quantity,
            unit=UsageUnit(input_dto.unit),
            cost_usd=input_dto.cost_usd,
            data=input_dto.data,
        )
        saved = await self._repo.save(event)

        await self._outbox.write(
            aggregate_type="UsageEvent",
            aggregate_id=saved.id,
            event_type="usage_event.recorded.v1",
            payload={
                "project_id": str(saved.project_id),
                "agent_id": str(saved.agent_id) if saved.agent_id else None,
                "event_type": saved.event_type,
                "quantity": saved.quantity,
                "unit": saved.unit,
            },
            routing_key="usage_event.recorded.v1",
            idempotency_key=f"metering:usage_event.recorded.v1:{saved.id}",
        )

        return RecordUsageOutput(event_id=saved.id)


class GetProjectDailyUsageUseCase:

    def __init__(self, repo: UsageDailyProjectRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        project_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DailyUsageResponse]:
        items = await self._repo.list_by_project(project_id, limit=limit, offset=offset)
        return [
            DailyUsageResponse(
                project_id=item.project_id,
                day=item.day,
                requests=item.requests,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                embedding_tokens=item.embedding_tokens,
                tool_calls=item.tool_calls,
                vector_queries=item.vector_queries,
                storage_mb=item.storage_mb,
                cost_usd=item.cost_usd,
            )
            for item in items
        ]


class GetAgentDailyUsageUseCase:

    def __init__(self, repo: UsageDailyAgentRepository) -> None:
        self._repo = repo

    async def execute(
        self,
        agent_id: UUID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DailyUsageResponse]:
        items = await self._repo.list_by_agent(agent_id, limit=limit, offset=offset)
        return [
            DailyUsageResponse(
                project_id=item.project_id,
                agent_id=item.agent_id,
                day=item.day,
                requests=item.requests,
                input_tokens=item.input_tokens,
                output_tokens=item.output_tokens,
                tool_calls=item.tool_calls,
                vector_queries=item.vector_queries,
                cost_usd=item.cost_usd,
            )
            for item in items
        ]
