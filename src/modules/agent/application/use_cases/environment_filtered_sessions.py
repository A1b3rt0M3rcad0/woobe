from __future__ import annotations

from modules.agent.application.dtos.runtime_dtos import (
    ListAgentSessionsOutput,
    ListAgentSessionsPageOutput,
)
from modules.agent.application.use_cases.runtime_use_cases import ListAgentSessionsUseCase
from modules.agent.domain.enums import RuntimeSessionMode, SessionStatus

_VALID_ENVIRONMENTS = {"draft", "staging", "production"}


def _session_environment(data) -> str:
    if not isinstance(data, dict):
        return "draft"
    value = data.get("runtime_environment")
    return value if value in _VALID_ENVIRONMENTS else "draft"


class EnvironmentFilteredListAgentSessionsUseCase(ListAgentSessionsUseCase):
    """Paginates Agent Sessions after applying the runtime-environment boundary."""

    async def execute(self, input_dto) -> ListAgentSessionsPageOutput:
        sessions = await self._session_repo.list_by_agent(
            input_dto.project_id,
            input_dto.agent_id,
        )
        environment = getattr(input_dto, "environment", None)
        if environment in _VALID_ENVIRONMENTS:
            sessions = [
                session
                for session in sessions
                if _session_environment(session.data) == environment
            ]

        sessions = sorted(
            sessions,
            key=lambda session: (session.last_message_at or session.created_at).timestamp()
            if session.last_message_at or session.created_at
            else 0.0,
            reverse=True,
        )

        start_index = 0
        if input_dto.cursor:
            for index, session in enumerate(sessions):
                if str(session.id) == input_dto.cursor:
                    start_index = index + 1
                    break

        page_sessions = sessions[start_index:start_index + input_dto.limit + 1]
        has_next = len(page_sessions) > input_dto.limit
        visible_sessions = page_sessions[:input_dto.limit]

        result: list[ListAgentSessionsOutput] = []
        for session in visible_sessions:
            try:
                count = await self._message_repo.count_by_session(session.id)
            except Exception:
                count = 0
            result.append(
                ListAgentSessionsOutput(
                    id=session.id,
                    project_id=session.project_id,
                    agent_id=session.agent_id,
                    status=SessionStatus(session.status),
                    mode=RuntimeSessionMode(session.mode),
                    data=session.data,
                    last_message_at=session.last_message_at,
                    created_at=session.created_at,
                    message_count=count,
                )
            )

        return ListAgentSessionsPageOutput(
            items=result,
            next_cursor=str(result[-1].id) if has_next and result else None,
            has_next=has_next,
        )
