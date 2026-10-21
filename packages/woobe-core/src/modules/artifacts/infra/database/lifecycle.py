"""Fenced, retryable Artifact retention and purge database phases."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import exists, func, or_, select, text, update

from modules.artifacts.domain.models import opaque_id
from modules.artifacts.infra.database.index_models import ArtifactDocumentIndexModel, ArtifactDocumentNodeModel
from modules.artifacts.infra.database.models import (
    ArtifactEventModel,
    ArtifactModel,
    CatalogOperationModel,
    GrantModel,
    HeadHistoryModel,
    ProcessingJobModel,
    RevisionModel,
    UploadModel,
    WorkspaceModel,
)
from modules.artifacts.infra.database.representation_models import (
    ArtifactRepresentationEntryModel,
    ArtifactRepresentationSetModel,
    ArtifactSourceBlockModel,
    ArtifactSourceSegmentModel,
    ArtifactStoredObjectModel,
)
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


LIFECYCLE_GRACE = timedelta(minutes=10)
ACTIVE_JOBS = ("queued", "running", "cancel_requested", "uncertain")
ACTIVE_UPLOADS = ("created", "uploading", "verifying")


@dataclass(frozen=True)
class StoredObjectReference:
    key: str
    version_id: str | None = None


@dataclass(frozen=True)
class ObjectCleanup:
    workspace_id: str
    storage_profile: str
    object_refs: tuple[StoredObjectReference, ...]

    @property
    def object_keys(self) -> tuple[str, ...]:
        return tuple(reference.key for reference in self.object_refs)


@dataclass(frozen=True)
class UploadCleanup(ObjectCleanup):
    upload_id: str
    part_keys: tuple[str, ...]


@dataclass(frozen=True)
class RevisionCleanup(ObjectCleanup):
    revision_id: str


class ArtifactLifecycleRepository:
    def __init__(self, engine, *, revision_grace: timedelta = LIFECYCLE_GRACE):
        self._engine = engine
        self._revision_grace = revision_grace

    async def mark_retention_expired(self, *, limit: int = 50) -> int:
        now = datetime.now(UTC)
        async with ArtifactsUnitOfWork(self._engine) as uow:
            statement = select(WorkspaceModel).where(
                WorkspaceModel.status == "archived",
                WorkspaceModel.archived_at.is_not(None),
                WorkspaceModel.archived_at
                <= now - WorkspaceModel.retention_days * text("interval '1 day'"),
            ).order_by(WorkspaceModel.archived_at, WorkspaceModel.id).limit(limit).with_for_update(skip_locked=True)
            rows = list((await uow.session.execute(statement)).scalars())
            for row in rows:
                row.status = "deletion_pending"
                row.deletion_requested_at = now
                row.version += 1
            await uow.session.flush()
            return len(rows)

    async def reconcile_restore_tombstones(self, workspace_ids: tuple[str, ...]) -> int:
        """Fail closed when a restored snapshot predates authoritative deletions.

        The operator supplies IDs from a newer, authoritative lifecycle ledger.
        Affected Workspaces are conservatively purged as a whole so an older
        snapshot cannot serve a revision that was current only at its checkpoint.
        """
        if not workspace_ids or len(workspace_ids) > 1000:
            raise ValueError("Restore tombstone batch must contain 1–1000 Workspaces")
        normalized = tuple(sorted({opaque_id(item) for item in workspace_ids}))
        now = datetime.now(UTC)
        async with ArtifactsUnitOfWork(self._engine) as uow:
            rows = list((await uow.session.execute(select(WorkspaceModel).where(
                WorkspaceModel.id.in_(normalized),
            ).order_by(WorkspaceModel.id).with_for_update(skip_locked=True))).scalars())
            changed = 0
            for workspace in rows:
                if workspace.status == "purged":
                    continue
                if workspace.status != "deletion_pending":
                    workspace.status = "deletion_pending"
                    workspace.version += 1
                    changed += 1
                    uow.session.add(ArtifactEventModel(
                        id=str(uuid4()), workspace_id=workspace.id,
                        operation_id=str(uuid4()), kind="artifact.workspace.restore_reconciled",
                        payload={"workspace_id": workspace.id},
                    ))
                cutoff = now - LIFECYCLE_GRACE
                if workspace.deletion_requested_at is None or workspace.deletion_requested_at > cutoff:
                    workspace.deletion_requested_at = cutoff
            await uow.session.flush()
            return changed

    async def multipart_upload_active(self, object_key: str, upload_id: str) -> bool:
        """Protect multipart writes owned by live upload intents or job fences."""
        parts = object_key.split("/")
        if (len(parts) < 10 or parts[0] != "projects" or parts[2] != "environments"
                or parts[4] != "artifact-workspaces"):
            return False
        workspace_id = parts[5]
        async with ArtifactsUnitOfWork(self._engine) as uow:
            if parts[6] == "artifacts" and len(parts) == 11 and parts[8] == "revisions":
                return (await uow.session.scalar(select(UploadModel.id).where(
                    UploadModel.workspace_id == workspace_id,
                    UploadModel.planned_revision_id == parts[9],
                    UploadModel.status.in_(ACTIVE_UPLOADS),
                    UploadModel.expires_at > datetime.now(UTC),
                ).limit(1))) is not None
            if (parts[6] == "processing" and len(parts) >= 11 and parts[8] == "attempts"
                    and parts[9].isdigit()):
                return (await uow.session.scalar(select(ProcessingJobModel.id).where(
                    ProcessingJobModel.workspace_id == workspace_id,
                    ProcessingJobModel.id == parts[7],
                    ProcessingJobModel.fencing_token == int(parts[9]),
                    ProcessingJobModel.status.in_(ACTIVE_JOBS),
                    ProcessingJobModel.lease_until > datetime.now(UTC),
                ).limit(1))) is not None
        return False

    async def expired_upload_cleanup(self, *, limit: int = 50) -> tuple[UploadCleanup, ...]:
        cutoff = datetime.now(UTC) - LIFECYCLE_GRACE
        async with ArtifactsUnitOfWork(self._engine) as uow:
            statement = select(UploadModel, WorkspaceModel.storage_profile, WorkspaceModel).join(
                WorkspaceModel, WorkspaceModel.id == UploadModel.workspace_id,
            ).where(
                UploadModel.status.in_(("aborted", "expired", "failed", "committed")),
                UploadModel.expires_at <= cutoff,
                func.jsonb_array_length(UploadModel.parts) > 0,
                WorkspaceModel.status != "purged",
            ).order_by(UploadModel.expires_at, UploadModel.id).limit(limit).with_for_update(
                skip_locked=True, of=UploadModel,
            )
            rows = list((await uow.session.execute(statement)).all())
            targets = []
            for row, storage_profile, workspace in rows:
                if any(
                    isinstance(part, dict)
                    and part.get("stored") is False
                    and self._recent_upload_part_io(part, cutoff)
                    for part in (row.parts or ())
                ):
                    continue
                references = {
                    str(part.get("key")): part.get("version_id")
                    for part in (row.parts or ())
                    if isinstance(part, dict) and part.get("key")
                }
                part_keys = tuple(sorted(references))
                if row.status != "committed":
                    references.setdefault(self._planned_object_key(workspace, row), None)
                targets.append(UploadCleanup(
                    row.workspace_id, storage_profile, self._object_references(references), row.id, part_keys,
                ))
            await uow.session.flush()
            return tuple(targets)

    @staticmethod
    def _recent_upload_part_io(part: dict, cutoff: datetime) -> bool:
        value = part.get("reserved_at")
        if not isinstance(value, str):
            return False
        try:
            reserved_at = datetime.fromisoformat(value)
        except ValueError:
            return False
        if reserved_at.tzinfo is None:
            return False
        return reserved_at > cutoff

    async def finish_upload_cleanup(self, target: UploadCleanup) -> bool:
        async with ArtifactsUnitOfWork(self._engine) as uow:
            row = (await uow.session.execute(select(UploadModel).where(
                UploadModel.workspace_id == target.workspace_id,
                UploadModel.id == target.upload_id,
            ).with_for_update())).scalar_one_or_none()
            if row is None or row.status not in {"aborted", "expired", "failed", "committed"}:
                return False
            # Keep object references until every delete succeeds. A failed
            # storage operation is retried from this same durable key list.
            keys = {str(part.get("key")) for part in (row.parts or ())
                    if isinstance(part, dict) and part.get("key")}
            if keys != set(target.part_keys):
                return False
            row.parts = []
            await uow.session.flush()
            return True

    async def due_revision_cleanup(self, *, limit: int = 50) -> tuple[RevisionCleanup, ...]:
        active_job = exists(select(ProcessingJobModel.id).where(
            ProcessingJobModel.workspace_id == RevisionModel.workspace_id,
            ProcessingJobModel.artifact_id == RevisionModel.artifact_id,
            ProcessingJobModel.revision_id == RevisionModel.id,
            ProcessingJobModel.status.in_(ACTIVE_JOBS),
        ))
        statement = select(RevisionModel, WorkspaceModel.storage_profile).join(
            WorkspaceModel, WorkspaceModel.id == RevisionModel.workspace_id,
        ).join(ArtifactModel,
            (ArtifactModel.workspace_id == RevisionModel.workspace_id)
            & (ArtifactModel.id == RevisionModel.artifact_id),
        ).where(
            WorkspaceModel.status.in_(("active", "archived")),
            RevisionModel.content_state.in_(("available", "deletion_pending")),
            RevisionModel.created_at <= func.now()
                - WorkspaceModel.retention_days * text("interval '1 day'")
                - self._revision_grace,
            or_(ArtifactModel.deleted.is_(True), ArtifactModel.revision_id != RevisionModel.id),
            ~active_job,
        ).order_by(RevisionModel.created_at, RevisionModel.id).limit(limit).with_for_update(
            skip_locked=True, of=RevisionModel,
        )
        async with ArtifactsUnitOfWork(self._engine) as uow:
            rows = list((await uow.session.execute(statement)).all())
            targets = []
            for revision, storage_profile in rows:
                revision.content_state = "deletion_pending"
                sets = list((await uow.session.execute(select(ArtifactRepresentationSetModel).where(
                    ArtifactRepresentationSetModel.workspace_id == revision.workspace_id,
                    ArtifactRepresentationSetModel.artifact_id == revision.artifact_id,
                    ArtifactRepresentationSetModel.revision_id == revision.id,
                    ArtifactRepresentationSetModel.status.in_(("building", "ready", "deletion_pending")),
                ).with_for_update())).scalars())
                set_ids = [item.id for item in sets]
                references = {revision.object_key: revision.storage_version_id}
                if set_ids:
                    stored = list((await uow.session.execute(select(ArtifactStoredObjectModel).where(
                        ArtifactStoredObjectModel.workspace_id == revision.workspace_id,
                        ArtifactStoredObjectModel.job_id.in_(select(ArtifactRepresentationSetModel.job_id).where(
                            ArtifactRepresentationSetModel.workspace_id == revision.workspace_id,
                            ArtifactRepresentationSetModel.id.in_(set_ids),
                        )),
                        ArtifactStoredObjectModel.state != "purged",
                    ).with_for_update())).scalars())
                    for item in stored:
                        references[item.object_key] = item.storage_version_id
                        if item.state in {"reserved", "stored", "referenced"}:
                            item.state = "gc_pending"
                    await uow.session.execute(update(ArtifactRepresentationSetModel).where(
                        ArtifactRepresentationSetModel.workspace_id == revision.workspace_id,
                        ArtifactRepresentationSetModel.id.in_(set_ids),
                    ).values(status="deletion_pending", sealed=False, diagnostics=[], pages=[]))
                    await uow.session.execute(update(ArtifactDocumentIndexModel).where(
                        ArtifactDocumentIndexModel.workspace_id == revision.workspace_id,
                        ArtifactDocumentIndexModel.representation_set_id.in_(set_ids),
                        ArtifactDocumentIndexModel.status.in_(("building", "ready", "deletion_pending")),
                    ).values(status="deletion_pending", sealed=False))
                    await uow.session.execute(update(ArtifactRepresentationEntryModel).where(
                        ArtifactRepresentationEntryModel.workspace_id == revision.workspace_id,
                        ArtifactRepresentationEntryModel.representation_set_id.in_(set_ids),
                    ).values(visible=False))
                targets.append(RevisionCleanup(
                    revision.workspace_id, storage_profile,
                    self._object_references(references), revision.id,
                ))
            await uow.session.flush()
            return tuple(targets)

    async def finish_revision_cleanup(self, target: RevisionCleanup) -> bool:
        async with ArtifactsUnitOfWork(self._engine) as uow:
            workspace = (await uow.session.execute(select(WorkspaceModel).where(
                WorkspaceModel.id == target.workspace_id,
            ).with_for_update())).scalar_one_or_none()
            revision = (await uow.session.execute(select(RevisionModel).where(
                RevisionModel.workspace_id == target.workspace_id,
                RevisionModel.id == target.revision_id,
            ).with_for_update())).scalar_one_or_none()
            if workspace is None or revision is None or revision.content_state == "purged":
                return False
            stored = list((await uow.session.execute(select(ArtifactStoredObjectModel).join(
                ArtifactRepresentationSetModel,
                (ArtifactRepresentationSetModel.workspace_id == ArtifactStoredObjectModel.workspace_id)
                & (ArtifactRepresentationSetModel.job_id == ArtifactStoredObjectModel.job_id),
            ).where(
                ArtifactRepresentationSetModel.workspace_id == target.workspace_id,
                ArtifactRepresentationSetModel.artifact_id == revision.artifact_id,
                ArtifactRepresentationSetModel.revision_id == revision.id,
                ArtifactStoredObjectModel.state != "purged",
            ).with_for_update())).scalars())
            used = revision.size_bytes + sum(
                item.size_bytes for item in stored if item.accounting_bucket == "used"
            )
            reserved = sum(item.size_bytes for item in stored if item.accounting_bucket == "reserved")
            if workspace.used_bytes < used or workspace.reserved_bytes < reserved:
                raise RuntimeError("Artifact retention accounting would underflow")
            workspace.used_bytes -= used
            workspace.reserved_bytes -= reserved
            revision.content_state = "purged"
            revision.source_refs = []
            revision.external_operation_ref = None
            for item in stored:
                item.state = "purged"
                item.accounting_bucket = "none"
            sets = list((await uow.session.execute(select(ArtifactRepresentationSetModel).where(
                ArtifactRepresentationSetModel.workspace_id == target.workspace_id,
                ArtifactRepresentationSetModel.artifact_id == revision.artifact_id,
                ArtifactRepresentationSetModel.revision_id == revision.id,
            ).with_for_update())).scalars())
            set_ids = [item.id for item in sets]
            if set_ids:
                for item in sets:
                    item.status, item.sealed, item.diagnostics, item.pages = "purged", False, [], []
                await uow.session.execute(update(ArtifactDocumentIndexModel).where(
                    ArtifactDocumentIndexModel.workspace_id == target.workspace_id,
                    ArtifactDocumentIndexModel.representation_set_id.in_(set_ids),
                ).values(status="purged", sealed=False))
                await uow.session.execute(update(ArtifactDocumentNodeModel).where(
                    ArtifactDocumentNodeModel.workspace_id == target.workspace_id,
                    ArtifactDocumentNodeModel.representation_set_id.in_(set_ids),
                ).values(title="Purged source", source_ranges=[], block_id=None, block_sha256=None))
                await uow.session.execute(update(ArtifactSourceSegmentModel).where(
                    ArtifactSourceSegmentModel.workspace_id == target.workspace_id,
                    ArtifactSourceSegmentModel.representation_set_id.in_(set_ids),
                ).values(search_text="", search_normalized=""))
                await uow.session.execute(update(ArtifactSourceBlockModel).where(
                    ArtifactSourceBlockModel.workspace_id == target.workspace_id,
                    ArtifactSourceBlockModel.representation_set_id.in_(set_ids),
                ).values(source_locator={}, asset_ids=[]))
            uow.session.add(ArtifactEventModel(
                id=str(uuid4()), workspace_id=target.workspace_id,
                operation_id=str(uuid4()), kind="artifact.revision.purged",
                payload={"artifact_id": revision.artifact_id, "revision_id": revision.id},
            ))
            await uow.session.flush()
            return True

    async def pending_workspace_cleanup(self, *, limit: int = 20) -> tuple[ObjectCleanup, ...]:
        now = datetime.now(UTC)
        grace_cutoff = now - LIFECYCLE_GRACE
        async with ArtifactsUnitOfWork(self._engine) as uow:
            workspaces = list((await uow.session.execute(select(WorkspaceModel).where(
                WorkspaceModel.status == "deletion_pending",
                WorkspaceModel.deletion_requested_at.is_not(None),
                WorkspaceModel.deletion_requested_at <= grace_cutoff,
            ).order_by(WorkspaceModel.deletion_requested_at, WorkspaceModel.id).limit(limit)
                .with_for_update(skip_locked=True))).scalars())
            targets = []
            for workspace in workspaces:
                queued = (await uow.session.execute(select(ProcessingJobModel).where(
                    ProcessingJobModel.workspace_id == workspace.id,
                    ProcessingJobModel.status == "queued",
                ).with_for_update(skip_locked=True))).scalars()
                for job in queued:
                    job.status = "cancelled"
                    job.error_code = "WORKSPACE_DELETION_REQUESTED"
                expired = list((await uow.session.execute(select(UploadModel).where(
                    UploadModel.workspace_id == workspace.id,
                    UploadModel.status.in_(ACTIVE_UPLOADS),
                    UploadModel.expires_at <= now,
                ).with_for_update(skip_locked=True))).scalars())
                for upload in expired:
                    workspace.reserved_bytes -= upload.expected_size
                    upload.status = "expired"
                active_jobs = await uow.session.scalar(select(func.count()).select_from(ProcessingJobModel).where(
                    ProcessingJobModel.workspace_id == workspace.id,
                    ProcessingJobModel.status.in_(ACTIVE_JOBS),
                ))
                uploads = list((await uow.session.execute(select(UploadModel).where(
                    UploadModel.workspace_id == workspace.id,
                ).with_for_update(skip_locked=True))).scalars())
                active_uploads = any(
                    upload.status in ACTIVE_UPLOADS
                    or (upload.status == "expired" and upload.expires_at > grace_cutoff)
                    or any(self._recent_upload_part_io(part, grace_cutoff)
                           for part in (upload.parts or ()) if isinstance(part, dict))
                    for upload in uploads
                )
                if active_jobs or active_uploads:
                    continue
                revisions = list((await uow.session.execute(select(RevisionModel).where(
                    RevisionModel.workspace_id == workspace.id,
                ).with_for_update())).scalars())
                references = {item.object_key: item.storage_version_id for item in revisions}
                for upload in uploads:
                    references.update({
                        str(part.get("key")): part.get("version_id")
                        for part in (upload.parts or ())
                        if isinstance(part, dict) and part.get("key")
                    })
                    if upload.status != "committed":
                        references.setdefault(self._planned_object_key(workspace, upload), None)
                stored = list((await uow.session.execute(select(ArtifactStoredObjectModel).where(
                    ArtifactStoredObjectModel.workspace_id == workspace.id,
                ).with_for_update())).scalars())
                references.update({item.object_key: item.storage_version_id for item in stored})
                for item in revisions:
                    item.content_state = "deletion_pending"
                for item in stored:
                    if item.state != "purged":
                        item.state = "gc_pending"
                targets.append(ObjectCleanup(
                    workspace.id, workspace.storage_profile, self._object_references(references),
                ))
            await uow.session.flush()
            return tuple(targets)

    @staticmethod
    def _planned_object_key(workspace, upload) -> str:
        return (
            f"projects/{workspace.project_id}/environments/{workspace.environment}/"
            f"artifact-workspaces/{workspace.id}/artifacts/{upload.artifact_id}/"
            f"revisions/{upload.planned_revision_id}/original"
        )

    @staticmethod
    def _object_references(objects: dict[str, str | None]) -> tuple[StoredObjectReference, ...]:
        return tuple(StoredObjectReference(key, objects[key]) for key in sorted(objects))

    async def finish_workspace_cleanup(self, target: ObjectCleanup) -> bool:
        async with ArtifactsUnitOfWork(self._engine) as uow:
            workspace = (await uow.session.execute(select(WorkspaceModel).where(
                WorkspaceModel.id == target.workspace_id,
            ).with_for_update())).scalar_one_or_none()
            if workspace is None or workspace.status == "purged":
                return False
            if workspace.status != "deletion_pending":
                return False
            await uow.session.execute(update(RevisionModel).where(
                RevisionModel.workspace_id == workspace.id,
            ).values(content_state="purged", source_refs=[], external_operation_ref=None))
            await uow.session.execute(update(ArtifactStoredObjectModel).where(
                ArtifactStoredObjectModel.workspace_id == workspace.id,
            ).values(state="purged", accounting_bucket="none"))
            await uow.session.execute(update(ArtifactRepresentationSetModel).where(
                ArtifactRepresentationSetModel.workspace_id == workspace.id,
            ).values(status="purged", sealed=False, diagnostics=[], pages=[]))
            await uow.session.execute(update(ArtifactDocumentIndexModel).where(
                ArtifactDocumentIndexModel.workspace_id == workspace.id,
            ).values(status="purged", sealed=False))
            await uow.session.execute(update(ArtifactRepresentationEntryModel).where(
                ArtifactRepresentationEntryModel.workspace_id == workspace.id,
            ).values(path=func.concat("[purged]/", ArtifactRepresentationEntryModel.id), visible=False, asset_id=None))
            await uow.session.execute(update(ArtifactSourceSegmentModel).where(
                ArtifactSourceSegmentModel.workspace_id == workspace.id,
            ).values(search_text="", search_normalized=""))
            await uow.session.execute(update(ArtifactSourceBlockModel).where(
                ArtifactSourceBlockModel.workspace_id == workspace.id,
            ).values(source_locator={}, asset_ids=[]))
            await uow.session.execute(update(ArtifactDocumentNodeModel).where(
                ArtifactDocumentNodeModel.workspace_id == workspace.id,
            ).values(title="Purged source", source_ranges=[], block_id=None, block_sha256=None))
            await uow.session.execute(update(ArtifactModel).where(
                ArtifactModel.workspace_id == workspace.id,
            ).values(path="[purged]", deleted=True, revision_id=None))
            await uow.session.execute(update(HeadHistoryModel).where(
                HeadHistoryModel.workspace_id == workspace.id,
            ).values(path="[purged]", deleted=True))
            await uow.session.execute(update(CatalogOperationModel).where(
                CatalogOperationModel.workspace_id == workspace.id,
            ).values(receipt={"purged": True}))
            await uow.session.execute(update(UploadModel).where(
                UploadModel.workspace_id == workspace.id,
            ).values(status="expired", path="", source_refs=[], parts=[], receipt=None))
            await uow.session.execute(update(ProcessingJobModel).where(
                ProcessingJobModel.workspace_id == workspace.id,
            ).values(recipe={}, result=None, checkpoints={}, model_binding=None))
            await uow.session.execute(update(GrantModel).where(
                GrantModel.workspace_id == workspace.id,
                GrantModel.revoked.is_(False),
            ).values(revoked=True, revision=GrantModel.revision + 1))
            uow.session.add(ArtifactEventModel(
                id=str(uuid4()), workspace_id=workspace.id,
                operation_id=str(uuid4()), kind="artifact.workspace.purged",
                payload={"workspace_id": workspace.id},
            ))
            workspace.status = "purged"
            workspace.version += 1
            workspace.used_bytes = 0
            workspace.reserved_bytes = 0
            workspace.name = "Purged Workspace"
            workspace.external_namespace = "purged"
            workspace.external_key = workspace.id
            workspace.labels = {}
            workspace.default_profile_id = None
            workspace.default_profile_revision = None
            await uow.session.flush()
            return True
