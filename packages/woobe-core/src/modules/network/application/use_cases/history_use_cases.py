from modules.network.application.dtos.history import (
    ListNetworkExecutionEventsInput,
    ListNetworkSessionMessagesInput,
    ListNetworkSessionsInput,
    NetworkExecutionEventOutput,
    NetworkMessageHistoryOutput,
    NetworkSessionHistoryOutput,
    ResetNetworkSessionContextInput,
)
from modules.network.application.interfaces.history_repository import (
    NetworkHistoryRepository,
)
from shared.contracts.errors import ConflictError, NotFoundError


class ListNetworkSessionsUseCase:
    def __init__(self, repository: NetworkHistoryRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListNetworkSessionsInput,
    ) -> list[NetworkSessionHistoryOutput]:
        return await self._repository.list_sessions(
            network_id=input_dto.network_id,
            project_id=input_dto.project_id,
            limit=100,
        )


class ListNetworkSessionMessagesUseCase:
    def __init__(self, repository: NetworkHistoryRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListNetworkSessionMessagesInput,
    ) -> list[NetworkMessageHistoryOutput]:
        if not await self._repository.session_exists(
            network_id=input_dto.network_id,
            network_session_id=input_dto.network_session_id,
            project_id=input_dto.project_id,
        ):
            raise NotFoundError("Network Session not found")
        return await self._repository.list_messages(
            network_session_id=input_dto.network_session_id,
            project_id=input_dto.project_id,
            offset=input_dto.offset,
            limit=input_dto.limit,
        )


class ResetNetworkSessionContextUseCase:
    def __init__(self, repository: NetworkHistoryRepository) -> None:
        self._repository = repository

    async def execute(self, input_dto: ResetNetworkSessionContextInput) -> None:
        if not await self._repository.session_exists(
            network_id=input_dto.network_id,
            network_session_id=input_dto.network_session_id,
            project_id=input_dto.project_id,
        ):
            raise NotFoundError("Network Session not found")
        if await self._repository.has_active_execution(input_dto.network_session_id):
            raise ConflictError("Wait for the active execution before resetting context")
        await self._repository.clear_agent_contexts(input_dto.network_session_id)


class ListNetworkExecutionEventsUseCase:
    def __init__(self, repository: NetworkHistoryRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: ListNetworkExecutionEventsInput,
    ) -> list[NetworkExecutionEventOutput]:
        if not await self._repository.execution_exists(
            execution_id=input_dto.execution_id,
            project_id=input_dto.project_id,
        ):
            raise NotFoundError("Network execution not found")
        return await self._repository.list_execution_events(
            execution_id=input_dto.execution_id,
            after_sequence=input_dto.after_sequence,
            limit=input_dto.limit,
        )
