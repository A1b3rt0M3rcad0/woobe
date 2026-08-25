from __future__ import annotations

from typing import Any

from modules.agent.domain.errors import AgentNotFoundError
from shared.contracts.errors import ValidationError


class SessionModeCompatibleCreateReleaseUseCase:
    """Requires an explicit snapshot mode while supporting legacy clients.

    New editors send session_mode as part of the Draft snapshot. Requests from
    older clients inherit the persisted Agent value once, so the resulting Draft
    is still explicit and future promotions are deterministic.
    """

    def __init__(self, delegate: Any, agent_repo: Any) -> None:
        self._delegate = delegate
        self._agent_repo = agent_repo

    async def execute(self, input_dto: Any, change_kind: str = "change") -> Any:
        session_mode = getattr(input_dto, "session_mode", None)
        if session_mode is None:
            agent = await self._agent_repo.get_by_id(input_dto.agent_id)
            if agent is None or agent.project_id != input_dto.project_id:
                raise AgentNotFoundError(input_dto.agent_id)
            session_mode = getattr(agent.session_mode, "value", agent.session_mode)
            input_dto = input_dto.model_copy(update={"session_mode": session_mode})

        if session_mode not in {"stateful", "stateless"}:
            raise ValidationError("Agent snapshot session_mode must be stateful or stateless")
        return await self._delegate.execute(input_dto, change_kind=change_kind)
