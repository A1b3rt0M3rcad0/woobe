from __future__ import annotations

from typing import Protocol

from modules.agent.application.dtos.runtime_dtos import AskInput, AskOutput


class AgentExecutionPort(Protocol):
    """Application boundary for executing one Agent interaction."""

    async def execute(self, input_dto: AskInput) -> AskOutput: ...
