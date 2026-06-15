from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID


class UsageRecorder(ABC):

    @abstractmethod
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
        ...
