from datetime import UTC, datetime, timedelta
import hashlib
import json
from uuid import uuid4

from sqlalchemy import select

from modules.artifacts.application.contracts.uploads import UploadRequest, UploadSnapshot, UploadView
from modules.artifacts.domain.models import (
    ArtifactError, ArtifactRef, Revision, UploadStatus, artifact_object_key,
)
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.models import ArtifactEventModel, ArtifactModel, UploadModel
from modules.artifacts.infra.database.representation_models import ArtifactRepresentationEntryModel, ArtifactRepresentationSetModel, ArtifactStoredObjectModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


TERMINAL = {'committed', 'aborted', 'expired', 'failed'}


class UploadRepository:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    def _snapshot(self, request, row, workspace):
        reference = ArtifactRef(**row.receipt) if row.receipt is not None else None
        view = UploadView(row.id, row.operation_id, row.workspace_id, row.offset,
                          row.expected_size, UploadStatus(row.status), row.expires_at, reference)
        key = artifact_object_key(request.scope, row.workspace_id,
                                  ArtifactRef(row.artifact_id, row.planned_revision_id))
        return UploadSnapshot(view, row.artifact_id, row.planned_revision_id, row.path,
            row.expected_sha256, row.content_type, workspace.storage_profile, key,
            tuple(dict(part) for part in row.parts), row.expected_revision,
            row.source_representation_set_id, row.source_representation_entry_id)

    async def _load(self, request, subject):
        # A single workspace lock serializes quota, cancellation and publication.
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id, lock=True)
        row = (await self._uow.session.execute(select(UploadModel).where(
            UploadModel.workspace_id == workspace.id, UploadModel.id == request.upload_id,
            UploadModel.principal_id == subject,
        ).with_for_update().execution_options(populate_existing=True))).scalar_one_or_none()
        if row is None:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Upload access is denied')
        if row.status not in TERMINAL and row.expires_at <= datetime.now(UTC):
            workspace.reserved_bytes -= row.expected_size
            row.status = 'expired'
        return row, workspace

    async def _validate_lineage(self, workspace_id, generation_id, entry_id, size, digest, content_type):
        if generation_id is None:
            return
        statement = select(ArtifactRepresentationEntryModel.id).join(ArtifactRepresentationSetModel,
            ArtifactRepresentationSetModel.id == ArtifactRepresentationEntryModel.representation_set_id).join(
            ArtifactStoredObjectModel, ArtifactStoredObjectModel.id == ArtifactRepresentationEntryModel.object_id).join(
            ArtifactModel, ArtifactModel.id == ArtifactRepresentationSetModel.artifact_id).where(
            ArtifactRepresentationEntryModel.id == entry_id,
            ArtifactRepresentationEntryModel.representation_set_id == generation_id,
            ArtifactRepresentationEntryModel.workspace_id == workspace_id,
            ArtifactRepresentationEntryModel.visible.is_(True), ArtifactModel.deleted.is_(False),
            ArtifactRepresentationSetModel.status == 'ready', ArtifactStoredObjectModel.state == 'referenced',
            ArtifactStoredObjectModel.size_bytes == size, ArtifactStoredObjectModel.sha256 == digest,
            ArtifactStoredObjectModel.content_type == content_type)
        if await self._uow.session.scalar(statement) is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Representation copy lineage is unavailable or differs')

    async def begin(self, request, subject):
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id, lock=True)
        definition = request.definition
        await self._validate_lineage(workspace.id, request.source_representation_set_id,
            request.source_representation_entry_id, definition.size_bytes, definition.sha256, definition.content_type)
        payload = definition.model_dump(mode='json')
        if (request.origin != 'upload' or request.run_id is not None or request.node_id is not None
            or request.producer_id is not None or request.external_operation_ref is not None
            or request.source_refs):
            payload = {'definition': payload, 'origin': request.origin,
                       'run_id': request.run_id, 'node_id': request.node_id,
                       'producer_id': request.producer_id,
                       'external_operation_ref': request.external_operation_ref,
                       'source_refs': list(request.source_refs)}
        if request.source_representation_set_id is not None:
            payload = {'request': payload, 'source_representation_set_id': request.source_representation_set_id,
                       'source_representation_entry_id': request.source_representation_entry_id}
        fingerprint = hashlib.sha256(json.dumps(payload,
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        previous = (await self._uow.session.execute(select(UploadModel).where(
            UploadModel.workspace_id == workspace.id,
            UploadModel.operation_id == definition.operation_id,
        ))).scalar_one_or_none()
        if previous is not None:
            if previous.principal_id != subject:
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Upload access is denied')
            if previous.request_fingerprint != fingerprint:
                raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Upload operation has a different request')
            loaded, workspace = await self._load(UploadRequest(request.principal, request.scope, request.workspace_id, previous.id), subject)
            return self._snapshot(request, loaded, workspace)
        if workspace.status != 'active':
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Workspace does not accept uploads')
        if workspace.used_bytes + workspace.reserved_bytes + definition.size_bytes > workspace.quota_bytes:
            raise ArtifactError('QUOTA_EXCEEDED', 'Artifact workspace storage quota exceeded')
        if definition.artifact_id is not None:
            artifact = await self._catalog.artifact_row(request.scope, workspace.id, definition.artifact_id)
            if artifact.revision_id != definition.expected_revision or artifact.path != definition.path or artifact.kind != 'file':
                raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Artifact revision changed')
        else:
            await self._path_available(workspace.id, definition.path)
        row = UploadModel(id=str(uuid4()), workspace_id=workspace.id,
            operation_id=definition.operation_id, principal_id=subject, request_fingerprint=fingerprint,
            expected_size=definition.size_bytes, expected_sha256=definition.sha256,
            content_type=definition.content_type, path=definition.path,
            artifact_id=definition.artifact_id or str(uuid4()), planned_revision_id=str(uuid4()),
            expected_revision=definition.expected_revision, offset=0, status='created',
            expires_at=datetime.now(UTC) + timedelta(hours=24), parts=[], origin=request.origin,
            run_id=request.run_id, node_id=request.node_id,
            source_representation_set_id=request.source_representation_set_id,
            source_representation_entry_id=request.source_representation_entry_id,
            producer_id=request.producer_id,
            external_operation_ref=request.external_operation_ref,
            source_refs=list(request.source_refs))
        workspace.reserved_bytes += definition.size_bytes
        self._uow.session.add(row)
        await self._uow.session.flush()
        return self._snapshot(request, row, workspace)

    async def _path_available(self, workspace_id, path):
        existing = (await self._uow.session.execute(select(ArtifactModel.id).where(
            ArtifactModel.workspace_id == workspace_id, ArtifactModel.path == path,
            ArtifactModel.deleted.is_(False),
        ))).scalar_one_or_none()
        if existing is not None:
            raise ArtifactError('ARTIFACT_PATH_CONFLICT', 'Artifact path is already occupied')

    async def load(self, request, subject):
        row, workspace = await self._load(request, subject)
        return self._snapshot(request, row, workspace)

    async def record_part(self, request, subject):
        row, workspace = await self._load(request, subject)
        if request.phase not in {'reserve', 'stored'}:
            raise ValueError('Invalid upload part persistence phase')
        identity = {'offset': request.offset, 'size': request.size, 'sha256': request.sha256, 'key': request.key}
        existing = next((part for part in row.parts or () if part.get('key') == request.key), None)
        if existing is not None and any(existing.get(key) != value for key, value in identity.items()):
            raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload part identity changed')
        if (existing is not None and request.phase == 'stored'
                and existing.get('version_id') not in {None, request.version_id}):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Upload storage version changed')
        if row.status in TERMINAL:
            return self._snapshot(request, row, workspace)
        if request.phase == 'reserve':
            if existing is not None:
                return self._snapshot(request, row, workspace)
            if row.status == 'verifying' or request.offset != row.offset:
                raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload offset changed')
            if len(row.parts or ()) >= 4096:
                raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Upload part count limit exceeded')
            if not 0 < request.size <= 8 * 1024 * 1024 or row.offset + request.size > row.expected_size:
                raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Part exceeds the expected upload size')
            row.parts = [*(row.parts or ()), {
                **identity, 'stored': False, 'reserved_at': datetime.now(UTC).isoformat(),
            }]
            row.status = 'uploading'
            return self._snapshot(request, row, workspace)
        if existing is not None and existing.get('stored') is True:
            return self._snapshot(request, row, workspace)
        if row.status == 'verifying' or request.offset != row.offset:
            raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload offset changed')
        if not 0 < request.size <= 8 * 1024 * 1024 or row.offset + request.size > row.expected_size:
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Part exceeds the expected upload size')
        if existing is None:
            # Keep compatibility with older internal callers, but normal
            # transfers persist an intent before object storage I/O.
            existing = {**identity, 'stored': False}
            row.parts = [*(row.parts or ()), existing]
        row.parts = [
            {key: value for key, value in {
                **part, 'stored': True, 'version_id': request.version_id,
            }.items()
             if key != 'reserved_at'} if part.get('key') == request.key else part
            for part in row.parts
        ]
        row.offset += request.size
        row.status = 'uploading'
        return self._snapshot(request, row, workspace)

    async def verify(self, request, subject):
        row, workspace = await self._load(request, subject)
        if row.status not in TERMINAL:
            if row.offset != row.expected_size:
                raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'Upload is incomplete')
            if any(part.get('stored') is False for part in row.parts or ()):
                raise ArtifactError('UPLOAD_OFFSET_CONFLICT', 'An upload part is not durably stored')
            row.status = 'verifying'
        return self._snapshot(request, row, workspace)

    async def commit(self, request, subject):
        row, workspace = await self._load(request, subject)
        if row.status in TERMINAL:
            return self._snapshot(request, row, workspace)
        if (row.status != 'verifying' or row.offset != row.expected_size
            or (request.size, request.sha256, request.content_type) != (
                row.expected_size, row.expected_sha256, row.content_type)):
            raise ArtifactError('UPLOAD_INTEGRITY_MISMATCH', 'Verified upload metadata does not match the intent')
        await self._validate_lineage(workspace.id, row.source_representation_set_id, row.source_representation_entry_id,
            row.expected_size, row.expected_sha256, row.content_type)
        if row.expected_revision is None:
            await self._path_available(workspace.id, row.path)
        snapshot = self._snapshot(request, row, workspace)
        # Release the reservation in this transaction only; publication failure
        # rolls the reservation back along with revision, history and event.
        workspace.reserved_bytes -= row.expected_size
        await self._catalog.publish_revision(request.scope, workspace.id, path=row.path,
            revision=Revision(row.planned_revision_id, row.artifact_id, snapshot.object_key,
                row.content_type, row.expected_size, row.expected_sha256, row.origin, row.producer_id or subject,
                request.version_id, row.operation_id, row.run_id, row.node_id, row.source_representation_set_id, row.source_representation_entry_id,
                row.external_operation_ref, tuple(row.source_refs or ())), expected_revision=row.expected_revision)
        row.status = 'committed'
        row.receipt = {'artifact_id': row.artifact_id, 'revision_id': row.planned_revision_id}
        self._uow.session.add(ArtifactEventModel(id=str(uuid4()), workspace_id=workspace.id,
            kind='artifact.revision.published', operation_id=row.id,
            payload={'artifact_id': row.artifact_id, 'revision_id': row.planned_revision_id,
                     'catalog_version': workspace.catalog_version}))
        await self._uow.session.flush()
        return self._snapshot(request, row, workspace)

    async def abort(self, request, subject):
        row, workspace = await self._load(request, subject)
        if row.status not in TERMINAL:
            row.status = 'aborted'
            workspace.reserved_bytes -= row.expected_size
        return self._snapshot(request, row, workspace)
