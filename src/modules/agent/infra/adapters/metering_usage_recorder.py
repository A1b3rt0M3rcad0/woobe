from __future__ import annotations

import importlib
import logging
from uuid import UUID

from modules.agent.domain.ports.usage_recorder import UsageRecorder

logger = logging.getLogger(__name__)


class MeteringUsageRecorder(UsageRecorder):

    def __init__(self, uow: object) -> None:
        self._uow = uow

    async def record_llm_request(
        self,
        project_id: UUID,
        agent_id: UUID,
        input_tokens: int,
        output_tokens: int,
        total_tokens: int,
        cost_usd: float,
        model: str,
    ) -> None:
        try:
            metering_entities = importlib.import_module("modules.metering.domain.entities")
            metering_enums = importlib.import_module("modules.metering.domain.enums")
            repos_mod = importlib.import_module("modules.metering.infra.database.repositories")

            event = metering_entities.UsageEvent(
                project_id=project_id,
                agent_id=agent_id,
                event_type=metering_enums.UsageEventType.llm_request,
                quantity=total_tokens or 0,
                unit=metering_enums.UsageUnit.token,
                cost_usd=cost_usd,
                data={
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "model": model,
                },
            )
            repo = repos_mod.SQLAlchemyUsageEventRepository(self._uow)
            await repo.save(event)
        except Exception:
            logger.exception("Failed to record usage via MeteringUsageRecorder")
