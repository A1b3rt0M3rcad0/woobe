from dataclasses import asdict
import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, or_, select, update

from modules.artifacts.application.contracts.files import FileSnapshot
from modules.artifacts.domain.models import Artifact, ArtifactError, ArtifactRef, logical_path
from modules.artifacts.infra.database.catalog import CatalogRepository, artifact_entity
from modules.artifacts.infra.database.models import (
    ArtifactEventModel, ArtifactModel, CatalogOperationModel, HeadHistoryModel,
)
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


class FileRepository:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    async def read(self, request):
        workspace = await self._catalog.workspace(request.scope, request.workspace_id)
        row = await self._catalog.artifact_row(request.scope, workspace.id, request.artifact_id)
        revision_id = request.revision_id or row.revision_id
        revision = await self._catalog.revision(request.scope, workspace.id,
            ArtifactRef(row.id, revision_id)) if revision_id else None
        if row.kind == 'directory' and request.revision_id is not None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Directory content is unavailable')
        return FileSnapshot(artifact_entity(row), revision, workspace.storage_profile)

    async def page(self, scope, workspace_id, *, directory, catalog_version, after, limit):
        workspace = await self._catalog.workspace(scope, workspace_id)
        if not 0 <= catalog_version <= workspace.catalog_version or not 1 <= limit <= 201:
            raise ArtifactError('ARTIFACT_INVALID_CURSOR', 'Invalid artifact catalog snapshot')
        prefix = directory + '/' if directory else ''
        query = select(HeadHistoryModel).join(ArtifactModel,
            ArtifactModel.id == HeadHistoryModel.artifact_id).where(
            HeadHistoryModel.workspace_id == workspace_id,
            HeadHistoryModel.from_catalog_version <= catalog_version,
            or_(HeadHistoryModel.until_catalog_version.is_(None), HeadHistoryModel.until_catalog_version > catalog_version),
            HeadHistoryModel.deleted.is_(False), ArtifactModel.deleted.is_(False),
            HeadHistoryModel.path.startswith(prefix, autoescape=True),
            ~func.substr(HeadHistoryModel.path, len(prefix) + 1).contains('/', autoescape=True),
        )
        if after is not None:
            query = query.where(HeadHistoryModel.artifact_id > after)
        rows = (await self._uow.session.execute(query.order_by(HeadHistoryModel.artifact_id).limit(limit))).scalars()
        return tuple(Artifact(row.artifact_id, workspace_id, row.path, row.kind,
            row.revision_id, row.artifact_version) for row in rows)

    async def _history(self, workspace, row):
        await self._uow.session.execute(update(HeadHistoryModel).where(
            HeadHistoryModel.workspace_id == workspace.id, HeadHistoryModel.artifact_id == row.id,
            HeadHistoryModel.until_catalog_version.is_(None),
        ).values(until_catalog_version=workspace.catalog_version))
        self._uow.session.add(HeadHistoryModel(id=str(uuid4()), workspace_id=workspace.id,
            artifact_id=row.id, from_catalog_version=workspace.catalog_version,
            until_catalog_version=None, path=row.path, kind=row.kind,
            revision_id=row.revision_id, artifact_version=row.version, deleted=row.deleted))

    async def mutate(self, request, subject):
        workspace = await self._catalog.workspace_row(request.scope, request.workspace_id, lock=True)
        values = {'kind': request.kind, 'artifact_id': request.artifact_id,
                  'expected_version': request.expected_version, 'path': request.path}
        fingerprint = hashlib.sha256(json.dumps(values, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        previous = (await self._uow.session.execute(select(CatalogOperationModel).where(
            CatalogOperationModel.workspace_id == workspace.id,
            CatalogOperationModel.operation_id == request.operation_id))).scalar_one_or_none()
        if previous is not None:
            if previous.principal_id != subject:
                raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Operation access is denied')
            if previous.request_fingerprint != fingerprint:
                raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Operation has a different request')
            return Artifact(**previous.receipt)
        if request.kind == 'mkdir':
            await self._catalog.validate_path(workspace.id, request.path, kind='directory')
            row = ArtifactModel(id=str(uuid4()), workspace_id=workspace.id, path=request.path,
                                kind='directory', version=1, deleted=False)
            self._uow.session.add(row)
            await self._uow.session.flush()
            affected = [row]
        else:
            row = await self._catalog.artifact_row(request.scope, workspace.id, request.artifact_id)
            if row.version != request.expected_version:
                raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Artifact version changed')
            children = list((await self._uow.session.execute(select(ArtifactModel).where(
                ArtifactModel.workspace_id == workspace.id, ArtifactModel.deleted.is_(False),
                ArtifactModel.path.startswith(row.path + '/', autoescape=True),
            ).limit(1001))).scalars()) if row.kind == 'directory' else []
            if request.kind == 'delete':
                if children:
                    raise ArtifactError('ARTIFACT_PATH_CONFLICT', 'Directory is not empty')
                row.deleted = True
                row.version += 1
                affected = [row]
            else:
                if request.path == row.path:
                    affected = []
                else:
                    if request.path.startswith(row.path + '/'):
                        raise ArtifactError('ARTIFACT_PATH_CONFLICT', 'Cannot move an artifact into itself')
                    await self._catalog.validate_path(workspace.id, request.path, kind=row.kind)
                    if len(children) > 1000:
                        raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Directory move exceeds 1000 descendants')
                    affected = [row, *children]
                    old = row.path
                    for item in affected:
                        destination = request.path + item.path[len(old):]
                        logical_path(destination)
                        # A whole-tree move cannot merge into another tree.
                        await self._catalog.validate_path(workspace.id, destination, kind=item.kind)
                    for item in affected:
                        item.path = request.path + item.path[len(old):]
                        item.version += 1
        if affected:
            workspace.catalog_version += 1
            await self._catalog.ensure_parents(workspace, row.path)
            for item in affected:
                await self._history(workspace, item)
        result = artifact_entity(row)
        self._uow.session.add(CatalogOperationModel(id=str(uuid4()), workspace_id=workspace.id,
            principal_id=subject, operation_id=request.operation_id, request_fingerprint=fingerprint,
            receipt=asdict(result)))
        self._uow.session.add(ArtifactEventModel(id=str(uuid4()), workspace_id=workspace.id,
            operation_id=request.operation_id, kind=f'artifact.{request.kind}',
            payload={'artifact_id': row.id, 'catalog_version': workspace.catalog_version}))
        await self._uow.session.flush()
        return result
