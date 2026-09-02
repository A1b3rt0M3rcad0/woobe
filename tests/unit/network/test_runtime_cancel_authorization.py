from __future__ import annotations

from uuid import uuid4

import pytest

from modules.network.application.dtos.execution import (
    CancelNetworkExecutionInput,
    NetworkExecutionControlState,
)
from modules.network.application.use_cases.execution_control_use_cases import (
    CancelNetworkExecutionUseCase,
)
from shared.contracts.errors import NotFoundError


class _Repository:
    def __init__(self, execution: NetworkExecutionControlState) -> None:
        self.execution = execution

    async def get_execution(self, *, execution_id, project_id):
        if execution_id != self.execution.id or project_id != self.execution.project_id:
            return None
        return self.execution

    async def request_durable_cancellation(self, *, execution_id, project_id):
        if execution_id != self.execution.id or project_id != self.execution.project_id:
            return None
        return self.execution.model_copy(update={"status": "cancelled"})


class _RuntimeControl:
    def __init__(self) -> None:
        self.state = {"status": "running", "phase": "network_execution"}
        self.requested: list[object] = []

    async def snapshot(self, _execution_id):
        return dict(self.state)

    async def request_cancel(self, execution_id):
        self.requested.append(execution_id)


def _execution() -> NetworkExecutionControlState:
    return NetworkExecutionControlState(
        id=uuid4(),
        network_id=uuid4(),
        network_session_id=uuid4(),
        project_id=uuid4(),
        environment="production",
        status="running",
    )


@pytest.mark.asyncio
async def test_network_runtime_cancel_authorizes_exact_target_and_environment() -> None:
    execution = _execution()
    runtime = _RuntimeControl()
    use_case = CancelNetworkExecutionUseCase(_Repository(execution), runtime)

    result = await use_case.execute(
        CancelNetworkExecutionInput(
            execution_id=execution.id,
            project_id=execution.project_id,
            expected_network_id=execution.network_id,
            expected_environment=execution.environment,
        )
    )

    assert result.status == "cancel_requested"
    assert runtime.requested == [execution.id]


@pytest.mark.asyncio
async def test_network_runtime_cancel_rejects_execution_from_another_project() -> None:
    execution = _execution()
    use_case = CancelNetworkExecutionUseCase(_Repository(execution), _RuntimeControl())

    with pytest.raises(NotFoundError):
        await use_case.execute(
            CancelNetworkExecutionInput(
                execution_id=execution.id,
                project_id=uuid4(),
                expected_network_id=execution.network_id,
                expected_environment=execution.environment,
            )
        )


@pytest.mark.asyncio
async def test_network_runtime_cancel_hides_execution_from_wrong_target() -> None:
    execution = _execution()
    use_case = CancelNetworkExecutionUseCase(_Repository(execution), _RuntimeControl())

    with pytest.raises(NotFoundError):
        await use_case.execute(
            CancelNetworkExecutionInput(
                execution_id=execution.id,
                project_id=execution.project_id,
                expected_network_id=uuid4(),
                expected_environment=execution.environment,
            )
        )


@pytest.mark.asyncio
async def test_network_runtime_cancel_hides_execution_from_wrong_environment() -> None:
    execution = _execution()
    use_case = CancelNetworkExecutionUseCase(_Repository(execution), _RuntimeControl())

    with pytest.raises(NotFoundError):
        await use_case.execute(
            CancelNetworkExecutionInput(
                execution_id=execution.id,
                project_id=execution.project_id,
                expected_network_id=execution.network_id,
                expected_environment="staging",
            )
        )
