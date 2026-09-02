from modules.network.application.dtos.rerun import (
    RerunNetworkExecutionInput,
    RerunNetworkExecutionOutput,
)
from modules.network.application.interfaces.rerun_repository import (
    NetworkRerunRepository,
)
from shared.contracts.errors import ConflictError, NotFoundError


_ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


class RerunNetworkExecutionUseCase:
    def __init__(self, repository: NetworkRerunRepository) -> None:
        self._repository = repository

    async def execute(
        self,
        input_dto: RerunNetworkExecutionInput,
    ) -> RerunNetworkExecutionOutput:
        source = await self._repository.get_source(
            input_dto.execution_id,
            input_dto.project_id,
        )
        if source is None:
            raise NotFoundError("Network execution not found")
        if source.status in _ACTIVE_STATUSES:
            raise ConflictError("An active Network execution cannot be rerun")

        if input_dto.idempotency_key:
            existing = await self._repository.find_idempotent_execution(
                source.network_id,
                input_dto.idempotency_key,
            )
            if existing is not None:
                return RerunNetworkExecutionOutput(
                    execution_id=existing.id,
                    rerun_of_execution_id=source.id,
                    status=existing.status,
                )

        active_execution_id = await self._repository.find_active_execution_id(
            source.network_session_id
        )
        if active_execution_id is not None:
            raise ConflictError(
                f"Network Session already has an active execution: {active_execution_id}"
            )

        session = await self._repository.get_session_state(source.network_session_id)
        if session is None or session.status != "active":
            raise ConflictError("Network Session is not active")

        rerun = await self._repository.create_rerun(
            source,
            environment=session.environment,
            idempotency_key=input_dto.idempotency_key,
        )
        return RerunNetworkExecutionOutput(
            execution_id=rerun.id,
            rerun_of_execution_id=source.id,
            status=rerun.status,
        )
