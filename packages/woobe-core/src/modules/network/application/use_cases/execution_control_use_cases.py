from modules.network.application.dtos.execution import (
    CancelNetworkExecutionInput,
    NetworkExecutionControlState,
)
from modules.network.application.interfaces.execution_control import (
    NetworkExecutionControlRepository,
    NetworkExecutionRuntimeControl,
)
from shared.contracts.errors import NotFoundError


_TERMINAL_STATUSES = {"completed", "failed", "cancelled", "timed_out", "uncertain"}


def _runtime_is_terminal(state: dict) -> bool:
    status = str(state.get("status") or "")
    return (
        status == "terminal_pending_persist"
        or state.get("phase") == "persisted"
        or status in _TERMINAL_STATUSES
    )


class CancelNetworkExecutionUseCase:
    def __init__(
        self,
        repository: NetworkExecutionControlRepository,
        runtime_control: NetworkExecutionRuntimeControl,
    ) -> None:
        self._repository = repository
        self._runtime_control = runtime_control

    async def execute(
        self,
        input_dto: CancelNetworkExecutionInput,
    ) -> NetworkExecutionControlState:
        execution = await self._repository.get_execution(
            execution_id=input_dto.execution_id,
            project_id=input_dto.project_id,
        )
        if execution is None:
            raise NotFoundError("Network execution not found")
        if (
            input_dto.expected_network_id is not None
            and execution.network_id != input_dto.expected_network_id
        ):
            raise NotFoundError("Network execution not found")
        if (
            input_dto.expected_environment is not None
            and execution.environment != input_dto.expected_environment
        ):
            raise NotFoundError("Network execution not found")
        if execution.status in _TERMINAL_STATUSES:
            return execution

        state = await self._runtime_control.snapshot(execution.id)
        if state:
            if _runtime_is_terminal(state):
                return execution
            await self._runtime_control.request_cancel(execution.id)
            return execution.model_copy(update={"status": "cancel_requested"})

        durable = await self._repository.request_durable_cancellation(
            execution_id=execution.id,
            project_id=execution.project_id,
        )
        if durable is None:
            raise NotFoundError("Network execution not found")

        # Close the acceptance/worker race: Redis may be initialized after the first
        # lookup while PostgreSQL is applying queued cancellation.
        state = await self._runtime_control.snapshot(execution.id)
        if state and not _runtime_is_terminal(state):
            await self._runtime_control.request_cancel(execution.id)
        return durable
