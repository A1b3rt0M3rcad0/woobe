from uuid import UUID

from modules.agent.application.dtos import CreateReleaseInput
from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from shared.presentation.contracts import OperationOutcome, OperationResult


class CandidateSnapshotController:
    def __init__(self, use_case):
        self.use_case = use_case

    async def handle(self, request):
        body = dict(request.body)
        snapshot_id = UUID(body.pop("candidate_snapshot_id"))
        body["version"] = snapshot_id.hex
        snapshot = await self.use_case.execute(CreateReleaseInput(**body), snapshot_id=snapshot_id)
        # Native dependency IDs and a complete executable hash are preparation
        # evidence. They do not update a Source binding or environment selection.
        return OperationResult(outcome=OperationOutcome.CREATED, body={"success": True, "data": {
            "id": str(snapshot.id), "agent_id": str(snapshot.agent_id),
            "snapshot_kind": "candidate", "runtime_digest": "sha256:" + hash_agent_execution_snapshot(snapshot),
            "configuration_ready": True, "execution_ready": True}})
