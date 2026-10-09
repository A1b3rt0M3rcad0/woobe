"""Agent-owned idempotent constituent copying; callers never write Agent tables."""
from types import SimpleNamespace

from shared.contracts.errors import ConflictError


class AgentFrozenPublicationGateway:
    def __init__(self, *, drafts, publisher, snapshots):
        if drafts.kind != "Agent":
            raise ValueError("Frozen Agent publication requires the Agent transaction owner")
        self.drafts, self.publisher, self.snapshots = drafts, publisher, snapshots

    async def inspect(self, *, project_id, resource_id, principal, snapshot_id):
        async with self.drafts._read() as session:
            await self.drafts.owner.inspect(session, project_id=project_id,
                resource_id=resource_id, principal=principal, kind="Agent",
                environment="staging", required_permission="agent:read")
            return await self.snapshots.read(session, project_id=project_id,
                resource_id=resource_id, snapshot_id=snapshot_id, expected_kind="candidate")

    async def publish(self, *, project_id, resource_id, principal, request):
        async with self.drafts.transactions.begin() as session:
            await self.drafts.owner.inspect(session, project_id=project_id,
                resource_id=resource_id, principal=principal, kind="Agent",
                environment="staging", lock=True, required_permission="agent:version")
            digest, replay = await self.drafts._operation(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request,
                action="publish_network_constituent")
            if replay is not None:
                return replay
            native = await self.publisher.publish(session=session, project_id=project_id,
                resource_id=resource_id, principal=principal, reason=request.reason,
                candidate=SimpleNamespace(root_snapshot_id=request.snapshot_id,
                    runtime_digest=request.expected_runtime_digest))
            if native["runtime_digest"] != request.expected_runtime_digest:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: constituent copy differs")
            frozen = await self.snapshots.read(session, project_id=project_id,
                resource_id=resource_id, snapshot_id=native["release_id"], expected_kind="release")
            if frozen["runtime_digest"] != request.expected_runtime_digest:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: stored constituent differs")
            result = {"schema_version": "1.0", "kind": "Agent",
                "release_snapshot": frozen["runtime_snapshot"],
                "release_status": frozen["release_status"],
                "project_id": str(project_id), "resource_id": str(resource_id),
                "source_snapshot_id": str(request.snapshot_id),
                "release_id": str(native["release_id"]),
                "release_version": native["release_version"], "reused": native["reused"],
                "runtime_digest": native["runtime_digest"],
                "parent_operation_id": str(request.parent_operation_id),
                "parent_resource_id": str(request.parent_resource_id),
                "parent_candidate_id": str(request.parent_candidate_id),
                "parent_evaluation_id": str(request.parent_evaluation_id),
                "production_changed": False, "complete": True}
            return self.drafts._receipt(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request,
                digest=digest, result=result)
