"""Candidate record mechanics use lifecycle-owner transactions and gateways.

The preparation gateway owns closed-object semantic compilation and durable
native phases. It is injected by composition; this mechanism never imports an
Agent, Network or Package persistence implementation.
"""
from uuid import UUID

from sqlalchemy import select

from shared.contracts.asac_requests import ASaCRevision
from shared.contracts.errors import ConflictError, NotFoundError
from shared.infra.admin_idempotency import principal_identity


def candidate_output(row):
    return {"schema_version": "1.0", "candidate_id": str(row.id),
        "resource_id": str(row.resource_id), "resource_uid": str(row.resource_uid),
        "revision_id": row.revision_id, "record_digest": row.record_digest,
        "draft_id": str(row.draft_id), "draft_generation": row.draft_generation,
        "preparation_operation_id": str(row.preparation_operation_id),
        "state": row.state, "operation_id": str(row.operation_id), "write_outcome": "committed",
        "snapshot_id": str(row.root_snapshot_id) if row.root_snapshot_id else None,
        "runtime_digest": row.runtime_digest, "runtime_digest_scope": row.runtime_digest_scope, "production_changed": False,
        "published": False, "complete": row.state in {"ready", "rejected"}}


class ASaCCandidateStore:
    def __init__(self, *, drafts, candidates, preparation):
        self.drafts, self.candidates, self.preparation = drafts, candidates, preparation

    async def _authorize(self, session, project_id, resource_id, principal, *, write=False):
        return await self.drafts.owner.inspect(session, project_id=project_id,
            resource_id=resource_id, principal=principal, kind=self.drafts.kind,
            environment="staging", lock=write,
            required_permission=self.drafts.kind.lower() + (":version" if write else ":read"))

    async def _existing(self, session, project_id, resource_id, principal, request):
        digest, replay = await self.drafts._operation(session, project_id=project_id,
            resource_id=resource_id, principal=principal, request=request, action="stage")
        row = await session.scalar(select(self.candidates).where(
            self.candidates.project_id == project_id, self.candidates.resource_id == resource_id,
            self.candidates.actor == principal_identity(principal),
            self.candidates.operation_id == request.operation_id))
        if row is not None and row.request_digest != digest:
            raise ConflictError("ASAC_OPERATION_CONFLICT: candidate operation has another request")
        if bool(row) != bool(replay):
            raise ConflictError("ASAC_CANDIDATE_RECEIPT_INVALID: candidate and acceptance receipt disagree")
        return digest, replay

    async def _source(self, session, project_id, resource_id, request):
        line = await self.drafts._line(session, project_id, resource_id, request.draft_id)
        if line.generation != request.expected_generation:
            raise ConflictError("ASAC_DRAFT_CHANGED: candidate source generation is stale")
        row = await session.scalar(select(self.drafts.revisions).where(
            self.drafts.revisions.project_id == project_id,
            self.drafts.revisions.resource_id == resource_id,
            self.drafts.revisions.resource_uid == line.resource_uid,
            self.drafts.revisions.revision_id == request.revision_id))
        if row is None:
            raise NotFoundError("ASAC_REVISION_UNAVAILABLE")
        if line.working_revision_id != row.revision_id or line.artifact_id != row.artifact_id:
            raise ConflictError("ASAC_REVISION_MISMATCH: candidate source is not the selected sealed Draft")
        record = ASaCRevision.model_validate(row.document).model_dump(exclude_none=True)
        if record["kind"] != self.drafts.kind or record["resource_uid"] != str(line.resource_uid) or record["definition_digest"] != line.definition_digest:
            raise ConflictError("ASAC_REVISION_MISMATCH: owner source identity differs")
        if row.component_uids is None or row.provider_uids is None:
            raise ConflictError("ASAC_REVISION_MAPPING_UNAVAILABLE: create a new verified checkpoint with retained component identities")
        return line, row, record

    async def stage(self, *, project_id, resource_id, principal, request, api_origin):
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True)
            digest, replay = await self._existing(session, project_id, resource_id, principal, request)
            if replay is not None:
                return replay
            line, revision, record = await self._source(session, project_id, resource_id, request)
            source = {"artifact_id": str(revision.artifact_id), "record": record,
                "component_uids": dict(revision.component_uids), "provider_uids": dict(revision.provider_uids)}
        # Semantic inspection and object I/O must not keep an owner SQL lock.
        proposal = await self.preparation.prepare(project_id=project_id,
            resource_id=resource_id, principal=principal, request=request,
            source=source, kind=self.drafts.kind, api_origin=api_origin)
        async with self.drafts.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True)
            digest, replay = await self._existing(session, project_id, resource_id, principal, request)
            if replay is not None:
                return replay
            line, revision, current = await self._source(session, project_id, resource_id, request)
            if current != record or str(revision.artifact_id) != source["artifact_id"] or revision.component_uids != source["component_uids"] or revision.provider_uids != source["provider_uids"]:
                raise ConflictError("ASAC_DRAFT_CHANGED: source changed during candidate validation")
            # Acceptance is inserted through the injected gateway in this same
            # owner transaction. A receipt without its accepted native operation
            # or an operation without its candidate cannot become visible.
            operation = await self.preparation.accept(session=session,
                project_id=project_id, principal=principal, proposal=proposal)
            row = self.candidates(id=UUID(proposal["candidate_id"]),
                project_id=project_id, resource_id=resource_id, resource_uid=line.resource_uid,
                actor=principal_identity(principal), operation_id=request.operation_id,
                request_digest=digest, revision_id=revision.revision_id,
                record_digest=record["record_digest"], artifact_id=revision.artifact_id,
                draft_id=line.id, draft_generation=line.generation,
                preparation_operation_id=UUID(operation["operation_id"]), state="preparing",
                snapshot_ids=proposal["snapshot_ids"], native_bindings={}, runtime_fingerprints={})
            session.add(row)
            await session.flush()
            return self.drafts._receipt(session, project_id=project_id, resource_id=resource_id,
                principal=principal, request=request, digest=digest, result=candidate_output(row))

    async def get(self, *, project_id, resource_id, candidate_id, principal):
        async with self.drafts._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            row = await session.get(self.candidates, candidate_id)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_CANDIDATE_UNAVAILABLE")
            return candidate_output(row)


async def seal_candidate(session, model, *, project_id, resource_id, candidate_id,
                         preparation_operation_id, snapshot_id, runtime_digest,
                         native_bindings, runtime_fingerprints, runtime_digest_scope=None):
    """Called after native verification, in that owner's receipt transaction."""
    row = await session.get(model, candidate_id, with_for_update=True)
    if (row is None or row.project_id != project_id or row.resource_id != resource_id
        or row.preparation_operation_id != preparation_operation_id
        or str(snapshot_id) not in row.snapshot_ids.values()):
        raise ConflictError("ASAC_CANDIDATE_EVIDENCE_INVALID: verification belongs to another preparation")
    if row.state == "rejected":
        raise ConflictError("ASAC_CANDIDATE_REJECTED")
    if row.state == "ready":
        if (row.root_snapshot_id != snapshot_id or row.runtime_digest != runtime_digest
            or row.native_bindings != native_bindings or row.runtime_fingerprints != runtime_fingerprints):
            raise ConflictError("ASAC_CANDIDATE_IMMUTABLE: verification evidence changed")
        return candidate_output(row)
    row.root_snapshot_id, row.runtime_digest = snapshot_id, runtime_digest
    row.runtime_digest_scope = runtime_digest_scope
    row.native_bindings, row.runtime_fingerprints = native_bindings, runtime_fingerprints
    row.state = "ready"
    await session.flush()
    return candidate_output(row)
