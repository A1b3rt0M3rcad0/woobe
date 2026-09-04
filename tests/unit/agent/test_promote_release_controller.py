from __future__ import annotations

from uuid import uuid4

import pytest

from modules.agent.presentation.controllers.promote_release_controller import PromoteReleaseController
from shared.presentation.contracts import OperationRequest


class ReleaseStub:
    def __init__(self, *, agent_id):
        self.id = uuid4()
        self.project_id = uuid4()
        self.agent_id = agent_id
        self.version = "v0.0.20260622.00"
        self.status = "production"

    def __getattr__(self, _name):
        return None


class FakePromoteUseCase:
    def __init__(self) -> None:
        self.calls = []

    async def execute(self, agent_id, release_id, input_dto, **kwargs):
        self.calls.append(
            {
                "agent_id": agent_id,
                "release_id": release_id,
                "input_dto": input_dto,
                **kwargs,
            }
        )
        return ReleaseStub(agent_id=agent_id)


@pytest.mark.asyncio
async def test_controller_preserves_copy_snapshot_false_for_deploy() -> None:
    use_case = FakePromoteUseCase()
    controller = PromoteReleaseController(use_case)
    agent_id = uuid4()
    release_id = uuid4()

    response = await controller.handle(
        OperationRequest(
            path_params={"agent_id": str(agent_id), "release_id": str(release_id)},
            body={"target_status": "production", "copy_snapshot": False},
        )
    )

    assert response.outcome == "success"
    assert use_case.calls[0]["target_status"] == "production"
    assert use_case.calls[0]["copy_snapshot"] is False


@pytest.mark.asyncio
async def test_controller_preserves_copy_snapshot_true_for_new_release() -> None:
    use_case = FakePromoteUseCase()
    controller = PromoteReleaseController(use_case)
    agent_id = uuid4()
    release_id = uuid4()

    await controller.handle(
        OperationRequest(
            path_params={"agent_id": str(agent_id), "release_id": str(release_id)},
            body={"target_status": "production", "copy_snapshot": True},
        )
    )

    assert use_case.calls[0]["copy_snapshot"] is True
