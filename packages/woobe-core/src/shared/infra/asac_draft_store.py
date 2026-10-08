"""Transactional record mechanics parameterized by lifecycle-owner models.

Agent/Network authorize and own transactions. Package validates closed objects;
this adapter does not mutate native singleton Drafts or environment selections.
"""
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from shared.contracts.asac import asac_digest
from shared.contracts.errors import ConflictError, NotFoundError, ValidationError
from shared.infra.admin_idempotency import principal_identity


def draft_output(row):
    return {"schema_version": "1.0", "draft_id": str(row.id), "name": row.name,
            "resource_id": str(row.resource_id), "resource_uid": str(row.resource_uid),
            "generation": row.generation, "definition_digest": row.definition_digest,
            "artifact_id": str(row.artifact_id) if row.artifact_id else None,
            "working_revision_id": row.working_revision_id, "origin": row.origin,
            "write_environment": "draft", "production_changed": False,
            "content_status": "closed_artifact" if row.artifact_id else "legacy_native_draft",
            "semantic_validation": "stage_required", "complete": True}


class ASaCDraftStore:
    def __init__(self, *, transactions, kind, owner, drafts, revisions, operations, artifacts, identities, cursor_key=None):
        self.transactions, self.kind, self.owner = transactions, kind, owner
        self.drafts, self.revisions, self.operations, self.artifacts = drafts, revisions, operations, artifacts
        self.identities = identities
        self.cursor_key = cursor_key

    def _read(self):
        reader = getattr(self.transactions, "read", None)
        return reader() if reader else self.transactions.begin()

    async def _authorize(self, session, project_id, resource_id, principal, *, write=False, lock=False):
        return await self.owner.inspect(session, project_id=project_id, principal=principal,
            kind=self.kind, resource_id=resource_id, environment="draft", lock=lock,
            required_permission=self.kind.lower() + (":write" if write else ":read"))

    async def _operation(self, session, *, project_id, resource_id, principal, request, action):
        digest = asac_digest("operation", {"action": action, "payload": request.model_dump(mode="json", exclude_none=True)})
        row = await session.scalar(select(self.operations).where(
            self.operations.project_id == project_id, self.operations.resource_id == resource_id,
            self.operations.actor == principal_identity(principal), self.operations.operation_id == request.operation_id))
        if row and row.request_digest != digest:
            raise ConflictError("ASAC_OPERATION_CONFLICT: operation ID has another payload")
        return digest, row.result if row else None

    def _receipt(self, session, *, project_id, resource_id, principal, request, digest, result):
        result = {**result, "operation_id": str(request.operation_id), "write_outcome": "committed"}
        session.add(self.operations(project_id=project_id, resource_id=resource_id,
            actor=principal_identity(principal), operation_id=request.operation_id,
            request_digest=digest, result=result))
        return result

    async def open_draft(self, *, project_id, resource_id, principal, request):
        # Replaying a committed opening needs neither a new export nor its expired
        # temporary ticket. Authentication still precedes replay and every write.
        async with self.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="open")
            if replay is not None:
                return replay
        artifact = await self.artifacts.retain_export(project_id=project_id, principal=principal, export_id=request.source_export_id)
        if artifact["kind"] != self.kind or artifact["resource_id"] != str(resource_id):
            raise ConflictError("ASAC_ORIGIN_MISMATCH: export belongs to another native resource")
        source = artifact["source"]
        async with self.transactions.begin() as session:
            native = await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="open")
            if replay is not None:
                return replay
            if source.get("kind") == "draft" and source.get("draft_revision") != native["revision"]:
                raise ConflictError("ASAC_SOURCE_CHANGED: Draft changed after capture")
            # The owner locks the native root. A separate uniqueness constraint
            # arbitrates concurrent attempts to attach one UID to different roots.
            identity = await session.scalar(select(self.identities).where(
                self.identities.project_id == project_id,
                (self.identities.resource_id == resource_id) | (self.identities.resource_uid == request.resource_uid)))
            if identity is not None and (identity.resource_id != resource_id or identity.resource_uid != request.resource_uid):
                raise ConflictError("ASAC_IDENTITY_CONFLICT: logical UID has another native binding")
            if identity is None:
                session.add(self.identities(project_id=project_id, resource_id=resource_id, resource_uid=request.resource_uid))
                try:
                    await session.flush()
                except IntegrityError:
                    raise ConflictError("ASAC_IDENTITY_CONFLICT: concurrent logical UID binding") from None
            source_environment = source.get("environment") or source.get("kind")
            if source_environment == "release":
                source_environment = "production"
            if source_environment not in {"draft", "staging", "production"}:
                raise ValidationError("ASAC_ORIGIN_UNAVAILABLE: source environment is not verified")
            await self.owner.inspect(session, project_id=project_id, principal=principal,
                kind=self.kind, resource_id=resource_id, environment=source_environment)
            rows = (await session.scalars(select(self.drafts).where(
                self.drafts.project_id == project_id,
                (self.drafts.resource_id == resource_id) | (self.drafts.resource_uid == request.resource_uid)))).all()
            if any(row.resource_id != resource_id or row.resource_uid != request.resource_uid for row in rows):
                raise ConflictError("ASAC_IDENTITY_CONFLICT: logical UID is already linked to another native resource")
            if any(row.name == request.name for row in rows):
                raise ConflictError("ASAC_DRAFT_EXISTS: choose or open another Draft name")
            origin = {"origin_status": "captured_snapshot", "environment": source.get("environment"),
                      "snapshot_id": source.get("snapshot_id"), "snapshot_digest": source.get("snapshot_digest"),
                      "draft_generation": source.get("draft_revision"), "version": source.get("version")}
            if request.name != "default" and not any(row.name == "default" for row in rows):
                # Lazy migration preserves the existing native default rather than
                # replacing it with the historical hotfix's exported content.
                session.add(self.drafts(project_id=project_id, resource_id=resource_id,
                    resource_uid=request.resource_uid, name="default", generation=1,
                    origin={"origin_status": "unknown_origin", "environment": "draft", "native_generation": native["revision"]}))
            line = self.drafts(project_id=project_id, resource_id=resource_id,
                resource_uid=request.resource_uid, name=request.name, generation=1,
                artifact_id=UUID(artifact["artifact_id"]), definition_digest=artifact["definition_digest"], origin=origin)
            session.add(line)
            await session.flush()
            return self._receipt(session, project_id=project_id, resource_id=resource_id,
                principal=principal, request=request, digest=digest, result=draft_output(line))

    async def _line(self, session, project_id, resource_id, draft_id):
        line = await session.scalar(select(self.drafts).where(self.drafts.id == draft_id,
            self.drafts.project_id == project_id, self.drafts.resource_id == resource_id)
            .with_for_update().execution_options(populate_existing=True))
        if line is None or line.project_id != project_id or line.resource_id != resource_id:
            raise NotFoundError("ASAC_DRAFT_UNAVAILABLE: Draft is unavailable in this resource")
        return line

    async def save_draft(self, *, project_id, resource_id, draft_id, principal, request):
        async with self.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="save:" + str(draft_id))
            if replay is not None:
                return replay
        artifact = await self.artifacts.retain_upload(project_id=project_id, principal=principal,
            upload_id=request.upload_id, artifact_digest=request.artifact_digest)
        entry = artifact["manifest"]["spec"]["entrypoint"]
        if entry["kind"] != self.kind:
            raise ValidationError("ASAC_KIND_MISMATCH: closed object has another entrypoint kind")
        async with self.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="save:" + str(draft_id))
            if replay is not None:
                return replay
            line = await self._line(session, project_id, resource_id, draft_id)
            if line.generation != request.expected_generation:
                raise ConflictError("ASAC_DRAFT_CHANGED: expected Draft generation is stale")
            line.artifact_id = UUID(artifact["artifact_id"])
            if line.definition_digest != artifact["definition_digest"]:
                line.working_revision_id = None
            line.definition_digest = artifact["definition_digest"]
            line.generation += 1
            return self._receipt(session, project_id=project_id, resource_id=resource_id,
                principal=principal, request=request, digest=digest, result=draft_output(line))

    async def register_revision(self, *, project_id, resource_id, principal, request):
        # Only an already accepted exact Draft object can be checkpointed remotely.
        # Claimed client hashes and UUIDs are metadata, never binding authority.
        async with self.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="revision")
            if replay is not None:
                return replay
            line = await self._line(session, project_id, resource_id, request.draft_id)
            if line.generation != request.expected_generation:
                raise ConflictError("ASAC_DRAFT_CHANGED: expected Draft generation is stale")
            artifact_id, generation = line.artifact_id, line.generation
            if artifact_id is None:
                raise ConflictError("ASAC_DRAFT_UNSEALED: save a closed Draft first")
        artifact = await self.artifacts.get(project_id=project_id, principal=principal, artifact_id=artifact_id)
        record = request.record.model_dump(exclude_none=True)
        entry = artifact["manifest"]["spec"]["entrypoint"]
        if (record["kind"] != self.kind or record["artifact_digest"] != artifact["artifact_digest"]
            or record["definition_digest"] != artifact["definition_digest"]
            or set(request.component_uids) != set(artifact["component_digests"])
            or not set(request.provider_uids) <= set(artifact["provider_digests"])):
            raise ConflictError("ASAC_REVISION_MISMATCH: revision is not the verified closed Draft")
        uids = [*request.component_uids.values(), *request.provider_uids.values()]
        if len(set(uids)) != len(uids) or str(request.component_uids[entry["ref"]]) != record["resource_uid"]:
            raise ConflictError("ASAC_REVISION_MISMATCH: component identities are ambiguous")
        expected_components = {str(uid): artifact["component_digests"][key] for key, uid in request.component_uids.items()}
        expected_components.update({str(uid): artifact["provider_digests"][key] for key, uid in request.provider_uids.items()})
        if record["component_digests"] != expected_components:
            raise ConflictError("ASAC_REVISION_MISMATCH: component definitions differ from the captured object")
        async with self.transactions.begin() as session:
            await self._authorize(session, project_id, resource_id, principal, write=True, lock=True)
            digest, replay = await self._operation(session, project_id=project_id, resource_id=resource_id, principal=principal, request=request, action="revision")
            if replay is not None:
                return replay
            line = await self._line(session, project_id, resource_id, request.draft_id)
            if line.generation != generation or line.artifact_id != artifact_id or str(line.resource_uid) != record["resource_uid"]:
                raise ConflictError("ASAC_DRAFT_CHANGED: Draft changed during revision validation")
            existing = await session.scalar(select(self.revisions).where(self.revisions.project_id == project_id,
                self.revisions.resource_uid == line.resource_uid, self.revisions.revision_id == record["revision_id"]))
            if existing is not None and existing.document != record:
                raise ConflictError("ASAC_INTEGRITY_CONFLICT: immutable revision ID has different bytes or parents")
            for parent in record["parents"]:
                found = await session.scalar(select(self.revisions.id).where(self.revisions.project_id == project_id,
                    self.revisions.resource_id == resource_id, self.revisions.resource_uid == line.resource_uid,
                    self.revisions.revision_id == parent))
                if found is None:
                    raise ConflictError("ASAC_HISTORY_INCOMPLETE: register parent revisions before their children")
            if existing is None:
                session.add(self.revisions(project_id=project_id, resource_id=resource_id,
                    resource_uid=line.resource_uid, revision_id=record["revision_id"], artifact_id=artifact_id,
                    document=record, actor=principal_identity(principal)))
            line.working_revision_id = record["revision_id"]
            return self._receipt(session, project_id=project_id, resource_id=resource_id, principal=principal,
                request=request, digest=digest, result={"record": record, "author_artifact_status": "declared_not_retained" if record.get("author_artifact_digest") else "unavailable", "artifact_id": str(artifact_id),
                "draft_id": str(line.id), "generation": line.generation, "production_changed": False, "complete": True})

    async def list_drafts(self, *, project_id, resource_id, principal):
        async with self._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            rows = (await session.scalars(select(self.drafts).where(self.drafts.project_id == project_id,
                self.drafts.resource_id == resource_id).order_by(self.drafts.name).limit(201))).all()
            if len(rows) > 200:
                raise ValidationError("ASAC_DRAFT_LIMIT: Draft listing exceeds traversal limit")
            return {"drafts": [draft_output(row) for row in rows], "complete": True}

    async def get_draft(self, *, project_id, resource_id, draft_id, principal):
        async with self._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            row = await session.get(self.drafts, draft_id)
            if row is None or row.project_id != project_id or row.resource_id != resource_id:
                raise NotFoundError("ASAC_DRAFT_UNAVAILABLE")
            return draft_output(row)

    async def list_revisions(self, *, project_id, resource_id, principal, cursor=None, limit=100):
        from shared.infra.asac_revision_catalog import ASaCRevisionCatalog
        return await ASaCRevisionCatalog(self, self.cursor_key).fetch(project_id=project_id,
            resource_id=resource_id, principal=principal, cursor=cursor, limit=limit)

    async def get_revision(self, *, project_id, resource_id, revision_id, principal):
        async with self._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            row = await session.scalar(select(self.revisions).where(self.revisions.project_id == project_id,
                self.revisions.resource_id == resource_id, self.revisions.revision_id == revision_id))
            if row is None:
                raise NotFoundError("ASAC_REVISION_UNAVAILABLE")
            return {"record": row.document, "author_artifact_status": "declared_not_retained" if row.document.get("author_artifact_digest") else "unavailable", "artifact_id": str(row.artifact_id), "complete": True}

    async def operation(self, *, project_id, resource_id, operation_id, principal):
        async with self._read() as session:
            await self._authorize(session, project_id, resource_id, principal)
            row = await session.scalar(select(self.operations).where(self.operations.project_id == project_id,
                self.operations.resource_id == resource_id, self.operations.actor == principal_identity(principal),
                self.operations.operation_id == operation_id))
            if row is None:
                return {"operation_id": str(operation_id), "state": "not_observed", "write_outcome": "unknown", "retry_authorized": False, "complete": False}
            return {"operation_id": str(operation_id), "state": "committed", "result": row.result, "complete": True}
