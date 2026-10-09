"""Publication receipts share the lifecycle owner's native snapshot transaction."""
from datetime import UTC
from sqlalchemy import select
from shared.contracts.asac import asac_digest
from shared.contracts.asac_requests import ASaCRevision
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.admin_idempotency import principal_identity


def publication_output(row):
    data = {"schema_version":"1.0", "publication_id":str(row.id), "project_id":str(row.project_id),
        "resource_id":str(row.resource_id), "resource_uid":str(row.resource_uid),
        "operation_id":str(row.operation_id), "write_outcome":"committed", "state":"published",
        "candidate_id":str(row.candidate_id), "evaluation_id":str(row.evaluation_id),
        "release_id":str(row.release_id), "release_version":row.release_version, "reused":row.reused,
        "revision_id":row.revision_id, "actor":row.actor, "reason":row.reason,
        "created_at":row.created_at.replace(tzinfo=row.created_at.tzinfo or UTC).astimezone(UTC).isoformat(), **row.evidence,
        "published":True, "production_changed":False, "complete":True}
    data["receipt_digest"] = asac_digest("publication-receipt", data)
    return data


class ASaCPublicationStore:
    def __init__(self, *, evaluations, publications, publisher):
        self.evaluations, self.publications, self.publisher = evaluations, publications, publisher
        self.drafts = evaluations.drafts

    async def _authorize(self, session, project_id, resource_id, principal, *, write=False):
        await self.drafts.owner.inspect(session, project_id=project_id, resource_id=resource_id,
            principal=principal, kind=self.drafts.kind, environment="staging", lock=write,
            required_permission=self.drafts.kind.lower() + (":version" if write else ":read"))

    async def _proof(self, session, project_id, resource_id, request):
        candidate = await self.evaluations._candidate(session, project_id, resource_id, request.candidate_id)
        evaluation = await session.get(self.evaluations.evaluations, request.evaluation_id)
        if (evaluation is None or evaluation.project_id != project_id or evaluation.resource_id != resource_id
            or evaluation.candidate_id != candidate.id or evaluation.state != "passed"
            or evaluation.record_digest != candidate.record_digest or evaluation.runtime_digest != candidate.runtime_digest
            or evaluation.binding_digest != asac_digest("runtime-bindings", candidate.runtime_fingerprints)
            or not evaluation.cases or not all(case.get("state") == "passed" and case.get("evidence_digest") for case in evaluation.cases)):
            raise ConflictError("ASAC_PUBLICATION_EVALUATION_REQUIRED: qualification must prove this exact ready Candidate")
        revision = await session.scalar(select(self.drafts.revisions).where(
            self.drafts.revisions.project_id == project_id, self.drafts.revisions.resource_id == resource_id,
            self.drafts.revisions.resource_uid == candidate.resource_uid,
            self.drafts.revisions.revision_id == candidate.revision_id))
        if revision is None:
            raise NotFoundError("ASAC_REVISION_UNAVAILABLE")
        record = ASaCRevision.model_validate(revision.document).model_dump(exclude_none=True)
        if record["record_digest"] != candidate.record_digest or revision.artifact_id != candidate.artifact_id:
            raise ConflictError("ASAC_PUBLICATION_SOURCE_INVALID")
        return candidate, evaluation, record

    async def publish(self, *, project_id, resource_id, principal, request):
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True)
            digest, replay = await self.drafts._operation(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request, action="publish")
            if replay is not None:
                return replay
            candidate, evaluation, record = await self._proof(session, project_id, resource_id, request)
        fingerprints = await self.evaluations._bindings(candidate, project_id, principal)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True)
            digest, replay = await self.drafts._operation(session, project_id=project_id,
                resource_id=resource_id, principal=principal, request=request, action="publish")
            if replay is not None:
                return replay
            candidate, evaluation, current = await self._proof(session, project_id, resource_id, request)
            if fingerprints != candidate.runtime_fingerprints or current != record:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED")
            native = await self.publisher.publish(session=session, project_id=project_id,
                resource_id=resource_id, candidate=candidate, principal=principal, reason=request.reason)
            if native["runtime_digest"] != candidate.runtime_digest:
                raise ConflictError("ASAC_PUBLICATION_RUNTIME_CHANGED: native Release differs from tested snapshot")
            row = self.publications(project_id=project_id, resource_id=resource_id, resource_uid=candidate.resource_uid,
                candidate_id=candidate.id, evaluation_id=evaluation.id, release_id=native["release_id"],
                release_version=native["release_version"], revision_id=candidate.revision_id,
                actor=principal_identity(principal), operation_id=request.operation_id, request_digest=digest,
                reused=native["reused"], reason=request.reason, evidence={
                    "kind":self.drafts.kind,
                    "record_digest":candidate.record_digest, "runtime_digest":candidate.runtime_digest,
                    "definition_digest":record["definition_digest"], "artifact_digest":record["artifact_digest"],
                    "binding_digest":evaluation.binding_digest, "suite_digest":evaluation.suite_digest,
                    "dataset_digest":evaluation.dataset_digest, "policy_digest":evaluation.policy_digest,
                    "git": {"status":"declared", **request.git.model_dump()} if request.git else {"status":"unavailable"}})
            session.add(row)
            await session.flush()
            return self.drafts._receipt(session, project_id=project_id, resource_id=resource_id,
                principal=principal, request=request, digest=digest, result=publication_output(row))

    async def get(self, *, project_id, resource_id, publication_id, principal):
        async with self.drafts._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            row = await session.get(self.publications, publication_id)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_PUBLICATION_UNAVAILABLE")
            return publication_output(row)
