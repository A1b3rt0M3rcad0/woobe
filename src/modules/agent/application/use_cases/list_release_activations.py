from __future__ import annotations


class ListAgentReleaseActivationsUseCase:
    def __init__(self, activation_repo) -> None:
        self._activation_repo = activation_repo

    async def execute(self, agent_id):
        return await self._activation_repo.list_by_agent(agent_id)
