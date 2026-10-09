"""Package gateway for retained closure preparation, injected into owner Stage."""
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select

from modules.package.domain.errors import PackageError
from modules.package.infra.models import PackageResourceBindingModel, PackageSnapshotArtifactModel, PackageUploadModel, PackageOperationModel, PackagePlanModel
from modules.package.infra.snapshot_artifact_repository import PackageSnapshotArtifactRepository
from shared.infra.admin_idempotency import principal_identity


class PackageCandidatePreparation:
    def __init__(self, sessions, service):
        self.sessions, self.service = sessions, service
        self.retained = PackageSnapshotArtifactRepository(sessions, service.artifacts, service.exports)

    async def prepare(self, *, project_id, resource_id, principal, request, source, kind, api_origin):
        artifact_id = UUID(source["artifact_id"])
        evidence = await self.retained.get(project_id=project_id, principal=principal, artifact_id=artifact_id)
        record = source["record"]
        if (evidence["artifact_digest"] != record["artifact_digest"]
            or evidence["definition_digest"] != record["definition_digest"]
            or set(evidence["component_digests"]) != set(source["component_uids"])
            or any(record["component_digests"].get(uid) != evidence["component_digests"][key]
                   for key, uid in source["component_uids"].items())):
            raise PackageError("ASAC_REVISION_MISMATCH", "Candidate source differs from its retained closed object")
        # Capture verifies all bytes/inventory and graph closure. No dependency
        # is inferred from the CLI's current directory or a latest native Draft.
        bundle = await self.retained.capture(project_id=project_id, principal=principal, artifact_id=artifact_id)
        try:
            components = bundle.graph.components
            entry = bundle.graph.manifest["spec"]["entrypoint"]
            if entry["kind"] != kind or source["component_uids"][entry["ref"]] != record["resource_uid"]:
                raise PackageError("ASAC_REVISION_MISMATCH", "Candidate root identity differs from its sealed revision")
            root_keys = [key for key in bundle.graph.order if components[key]["kind"] in {"Agent", "Network"}]
            targets = {}
            async with self.sessions.begin() as session:
                for key in root_keys:
                    uid = UUID(source["component_uids"][key])
                    binding = await session.scalar(select(PackageResourceBindingModel).where(
                        PackageResourceBindingModel.project_id == project_id,
                        PackageResourceBindingModel.registry_id == request.registry_id,
                        PackageResourceBindingModel.resource_uid == uid))
                    if binding is None or binding.resource_id is None or binding.kind != components[key]["kind"]:
                        raise PackageError("ASAC_CANDIDATE_BINDING_UNAVAILABLE", "Resolve every native root identity before Stage")
                    if key == entry["ref"] and binding.resource_id != resource_id:
                        raise PackageError("ASAC_CANDIDATE_IDENTITY_INVALID", "Registry root differs from the lifecycle owner")
                    await self.service.plans.registry.inspect(session, project_id=project_id,
                        principal=principal, kind=binding.kind, resource_id=binding.resource_id)
                    targets[key] = {"kind": binding.kind, "resource_id": str(binding.resource_id),
                                    "resource_uid": str(uid)}
                retained = await session.get(PackageSnapshotArtifactModel, artifact_id)
                # A fresh short-lived actor-scoped planning ticket points to
                # retained custody. The original uploader and expiry confer no
                # continuing authority and cannot prevent authorized hydration.
                upload = PackageUploadModel(project_id=project_id, actor=principal_identity(principal),
                    artifact_digest=retained.artifact_digest, storage_key=retained.storage_key,
                    manifest=retained.manifest, inventory=retained.inventory,
                    size_bytes=retained.size_bytes, expires_at=datetime.now(UTC) + timedelta(hours=1))
                session.add(upload)
                await session.flush()
        finally:
            bundle.close()
        candidate_id = str(uuid4())
        snapshot_ids = {key: str(uuid4()) for key in root_keys}
        plan = await self.service.plans.create(project_id=project_id, principal=principal,
            upload_id=upload.id, artifact_digest=upload.artifact_digest,
            bindings=request.bindings, lifecycle="draft", release_notes=None, reason=None,
            api_origin=api_origin, mode="candidate", candidate={"candidate_id": candidate_id,
                "snapshot_ids": snapshot_ids, "targets": targets, "source": source})
        payload = {"plan_id": plan["plan_id"], "plan_digest": plan["plan_digest"],
            "upload_id": plan["upload_id"], "artifact_digest": plan["artifact_digest"],
            "lifecycle": "candidate", "bindings": request.bindings,
            "protected_bindings": {}, "release_notes": None, "reason": None}
        return {"candidate_id": candidate_id, "snapshot_ids": snapshot_ids,
                "key": "asac-stage:" + str(request.operation_id), "payload": payload}

    async def accept(self, *, session, project_id, principal, proposal):
        operation, _ = await self.service.operations.accept_in_session(session=session,
            project_id=project_id, principal=principal, key=proposal["key"], payload=proposal["payload"])
        return {"operation_id": str(operation.id)}

    async def verify_runtime_bindings(self, *, project_id, candidate_id,
                                      preparation_operation_id, principal,
                                      expected_fingerprints):
        # Retained evidence is independent of a planning ticket's expiry/actor.
        # Current permission and version checks remain mandatory for the caller.
        async with self.sessions() as session:
            operation = await session.get(PackageOperationModel, preparation_operation_id)
            plan = await session.get(PackagePlanModel, operation.plan_id) if operation else None
            if (operation is None or plan is None or operation.project_id != project_id
                or plan.project_id != project_id or operation.state != "succeeded"
                or plan.document.get("mode") != "candidate"
                or plan.document.get("candidate", {}).get("candidate_id") != str(candidate_id)):
                raise PackageError("ASAC_CANDIDATE_EVIDENCE_INVALID", "Retained native preparation evidence is unavailable")
            document = plan.document
        actual = await self.service.plans._inspector.inspect_bindings(
            project_id=project_id, principal=principal,
            requirements=document["source_definition"]["manifest"]["spec"].get("requires", {}),
            bindings=document["bindings"]["spec"])
        if actual != expected_fingerprints or actual != document["binding_resolutions"]:
            raise PackageError("ASAC_RUNTIME_BINDINGS_CHANGED", "Destination binding versions differ from the prepared candidate")
        return actual
