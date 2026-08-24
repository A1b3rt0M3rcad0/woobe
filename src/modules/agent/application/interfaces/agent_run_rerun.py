from __future__ import annotations

from typing import Protocol
from uuid import UUID

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput
from modules.agent.domain.run import AgentRun


class AgentRunRerunReader(Protocol):
    async def get_by_id(self, run_id: UUID) -> AgentRun | None: ...


class AgentRunExecutor(Protocol):
    async def execute(self, input_dto: AskInput) -> AskOutput: ...
