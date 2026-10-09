"""Read native roots and seal exact Candidate snapshots in Agent transactions."""
from uuid import UUID

from modules.agent.domain.execution_definition import hash_agent_execution_snapshot
from modules.agent.infra.database.asac_models import ASaCCandidateModel
from shared.contracts.errors import ConflictError
from shared.infra.asac_candidate_store import seal_candidate
from shared.presentation.contracts import OperationResult


class AgentCandidateLifecycleHandler:
    def __init__(self, uow, owner, releases):
        self.uow, self.owner, self.releases = uow, owner, releases

    async def handle(self, request):
        body = request.body
        project, agent_id = UUID(body["project_id"]), UUID(body["agent_id"])
        evidence = await self.owner.inspect(self.uow.session, project_id=project,
            resource_id=agent_id, principal=request.principal, kind="Agent",
            environment="staging", required_permission="agent:version" if body["action"] == "verify_candidate_closure" else "agent:read")
        if body["action"] == "resolve_candidate_root":
            result = {"id": str(agent_id), "revision": evidence["revision"]}
        else:
            snapshot_id = UUID(body["candidate_snapshot_id"])
            snapshot = await self.releases.get_by_id(snapshot_id)
            if (snapshot is None or snapshot.project_id != project or snapshot.agent_id != agent_id
                or getattr(snapshot, "snapshot_kind", None) != "candidate"):
                raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: exact native candidate snapshot is unavailable")
            runtime_digest = "sha256:" + hash_agent_execution_snapshot(snapshot)
            if runtime_digest != body["expected_runtime_digest"]:
                raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: native executable snapshot changed")
            result = await seal_candidate(self.uow.session, ASaCCandidateModel,
                project_id=project, resource_id=agent_id, candidate_id=UUID(body["candidate_id"]),
                preparation_operation_id=UUID(body["preparation_operation_id"]), snapshot_id=snapshot_id,
                runtime_digest=runtime_digest, native_bindings={"agent_id": str(agent_id), "snapshot_id": str(snapshot_id)},
                runtime_fingerprints=body["runtime_fingerprints"])
            result.update(configuration_ready=True, execution_ready=True)
        return OperationResult(body={"success": True, "data": result})
