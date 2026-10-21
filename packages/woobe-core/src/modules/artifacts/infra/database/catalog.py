"""Scoped catalog persistence. Callers own a short ArtifactsUnitOfWork."""

from dataclasses import asdict, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import exists, or_, select, update
from sqlalchemy.dialects.postgresql import insert

from modules.artifacts.domain.models import (
    Artifact, ArtifactError, ArtifactRef, Revision, Scope, Workspace, logical_path,
)
from modules.artifacts.infra.database.models import (
    ArtifactModel, GrantModel, HeadHistoryModel, RevisionModel, WorkspaceModel,
)
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


def workspace_entity(row: WorkspaceModel) -> Workspace:
    return Workspace(
        id=row.id, scope=Scope(str(row.project_id), row.environment),
        external_namespace=row.external_namespace, external_key=row.external_key,
        name=row.name, storage_profile=row.storage_profile, status=row.status,
        version=row.version, catalog_version=row.catalog_version,
        quota_bytes=row.quota_bytes, used_bytes=row.used_bytes,
        reserved_bytes=row.reserved_bytes, retention_days=row.retention_days,
        labels=tuple(sorted(row.labels.items())),
        default_profile_id=row.default_profile_id, default_profile_revision=row.default_profile_revision,
        archived_at=row.archived_at,
    )


def artifact_entity(row: ArtifactModel) -> Artifact:
    return Artifact(row.id, row.workspace_id, row.path, row.kind,
                    row.revision_id, row.version, row.deleted)


def revision_entity(row: RevisionModel) -> Revision:
    return Revision(row.id, row.artifact_id, row.object_key, row.content_type,
                    row.size_bytes, row.sha256, row.origin, row.producer_id, row.storage_version_id,
                    row.operation_id, row.run_id, row.node_id, row.source_representation_set_id,
                    row.source_representation_entry_id, row.external_operation_ref,
                    tuple(row.source_refs or ()), row.content_state)


class CatalogRepository:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow

    def _workspace_query(self, scope: Scope):
        return select(WorkspaceModel).where(
            WorkspaceModel.project_id == UUID(scope.project_id),
            WorkspaceModel.environment == scope.environment.value,
        )

    async def workspace_row(self, scope: Scope, workspace_id: str, *, lock: bool = False):
        query = self._workspace_query(scope).where(WorkspaceModel.id == workspace_id)
        if lock:
            query = query.with_for_update().execution_options(populate_existing=True)
        row = (await self._uow.session.execute(query)).scalar_one_or_none()
        if row is None or row.status == 'purged':
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact workspace is unavailable')
        return row

    async def workspace(self, scope: Scope, workspace_id: str) -> Workspace:
        return workspace_entity(await self.workspace_row(scope, workspace_id))

    async def insert_workspace(self, workspace: Workspace) -> Workspace:
        values = asdict(workspace)
        values.pop('scope')
        values['status'] = workspace.status.value
        values['labels'] = dict(workspace.labels)
        row = WorkspaceModel(**values, project_id=UUID(workspace.scope.project_id),
                             environment=workspace.scope.environment.value)
        self._uow.session.add(row)
        await self._uow.session.flush()
        return workspace_entity(row)

    async def provision_workspace(self, workspace: Workspace, fingerprint: str) -> tuple[Workspace, bool]:
        values = asdict(workspace)
        values.pop('scope')
        values.update(project_id=UUID(workspace.scope.project_id),
                      environment=workspace.scope.environment.value,
                      status=workspace.status.value, labels=dict(workspace.labels),
                      creation_fingerprint=fingerprint)
        created = (await self._uow.session.execute(insert(WorkspaceModel).values(**values)
                   .on_conflict_do_nothing(constraint='uq_artifact_workspace_external')
                   .returning(WorkspaceModel.id))).scalar_one_or_none()
        row = (await self._uow.session.execute(self._workspace_query(workspace.scope).where(
            WorkspaceModel.external_namespace == workspace.external_namespace,
            WorkspaceModel.external_key == workspace.external_key,
        ).with_for_update().execution_options(populate_existing=True))).scalar_one()
        if row.creation_fingerprint != fingerprint:
            raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Workspace identity already has a different creation request')
        return workspace_entity(row), created is not None

    async def resolve_workspace(self, scope: Scope, namespace: str, key: str) -> Workspace:
        row = (await self._uow.session.execute(self._workspace_query(scope).where(
            WorkspaceModel.external_namespace == namespace,
            WorkspaceModel.external_key == key, WorkspaceModel.status != 'purged',
        ))).scalar_one_or_none()
        if row is None:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
        return workspace_entity(row)

    async def accessible_workspaces(self, scope: Scope, principal_id: str, *,
                                     limit: int, after_id: str | None = None,
                                     namespace: str | None = None) -> tuple[Workspace, ...]:
        if not 1 <= limit <= 201:
            raise ValueError('Workspace page limit out of range')
        permitted = exists(select(GrantModel.id).where(
            GrantModel.project_id == WorkspaceModel.project_id,
            GrantModel.environment == WorkspaceModel.environment,
            GrantModel.principal_id == principal_id, GrantModel.revoked.is_(False),
            GrantModel.actions.contains(['read']),
            or_(GrantModel.expires_at.is_(None), GrantModel.expires_at > datetime.now(UTC)),
            or_(GrantModel.workspace_id == WorkspaceModel.id,
                GrantModel.external_namespace == WorkspaceModel.external_namespace),
        ))
        query = self._workspace_query(scope).where(permitted, WorkspaceModel.status.in_(['active', 'archived']))
        if after_id is not None:
            query = query.where(WorkspaceModel.id > after_id)
        if namespace is not None:
            query = query.where(WorkspaceModel.external_namespace == namespace)
        rows = (await self._uow.session.execute(query.order_by(WorkspaceModel.id).limit(limit))).scalars()
        return tuple(workspace_entity(row) for row in rows)

    async def update_workspace(self, scope: Scope, workspace_id: str, *, expected_version: int,
                               name: str | None = None, status: str | None = None,
                               labels: dict[str, str] | None = None) -> Workspace:
        row = await self.workspace_row(scope, workspace_id, lock=True)
        if row.version != expected_version:
            raise ArtifactError('WORKSPACE_REVISION_CONFLICT', 'Workspace version changed')
        if row.status == 'deletion_pending' and status not in {None, 'deletion_pending'}:
            raise ArtifactError('WORKSPACE_REVISION_CONFLICT', 'Deletion cannot be undone by a metadata update')
        current = workspace_entity(row)
        candidate = replace(current, name=name if name is not None else current.name,
                            status=status if status is not None else current.status,
                            labels=tuple(sorted(labels.items())) if labels is not None else current.labels)
        if candidate != current:
            row.name = candidate.name
            row.status = candidate.status.value
            row.labels = dict(candidate.labels)
            if candidate.status.value == 'archived' and current.status.value != 'archived':
                row.archived_at = datetime.now(UTC)
                row.deletion_requested_at = None
            elif candidate.status.value == 'active':
                row.archived_at = None
                row.deletion_requested_at = None
            elif candidate.status.value == 'deletion_pending' and current.status.value != 'deletion_pending':
                row.deletion_requested_at = datetime.now(UTC)
            row.version += 1
            await self._uow.session.flush()
        return workspace_entity(row)

    async def list_workspaces(self, scope: Scope, *, limit: int = 50,
                              after_id: str | None = None) -> tuple[Workspace, ...]:
        if not 1 <= limit <= 201:
            raise ValueError('Workspace page limit out of range')
        query = self._workspace_query(scope).where(WorkspaceModel.status != 'purged')
        if after_id is not None:
            query = query.where(WorkspaceModel.id > after_id)
        rows = (await self._uow.session.execute(query.order_by(WorkspaceModel.id).limit(limit))).scalars()
        return tuple(workspace_entity(row) for row in rows)

    async def artifact_row(self, scope: Scope, workspace_id: str, artifact_id: str, *, include_deleted: bool = False):
        query = (select(ArtifactModel).join(WorkspaceModel,
                 WorkspaceModel.id == ArtifactModel.workspace_id).where(
            WorkspaceModel.project_id == UUID(scope.project_id),
            WorkspaceModel.environment == scope.environment.value,
            WorkspaceModel.status.in_(['active', 'archived']),
            ArtifactModel.workspace_id == workspace_id,
            ArtifactModel.id == artifact_id,
        ))
        if not include_deleted:
            query = query.where(ArtifactModel.deleted.is_(False))
        row = (await self._uow.session.execute(query)).scalar_one_or_none()
        if row is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact is unavailable')
        return row

    async def revision(self, scope: Scope, workspace_id: str, reference: ArtifactRef, *, include_deleted: bool = False) -> Revision:
        artifact = await self.artifact_row(scope, workspace_id, reference.artifact_id, include_deleted=include_deleted)
        row = (await self._uow.session.execute(select(RevisionModel).where(
            RevisionModel.workspace_id == workspace_id,
            RevisionModel.artifact_id == artifact.id,
            RevisionModel.id == reference.revision_id,
        ))).scalar_one_or_none()
        if row is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact revision is unavailable')
        return revision_entity(row)

    async def visible_artifacts(self, scope: Scope, workspace_id: str, *,
                                catalog_version: int, limit: int = 50,
                                after_id: str | None = None) -> tuple[Artifact, ...]:
        workspace = await self.workspace(scope, workspace_id)
        if workspace.status not in {'active', 'archived'}:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact workspace is unavailable')
        if not 0 <= catalog_version <= workspace.catalog_version or not 1 <= limit <= 201:
            raise ValueError('Invalid catalog snapshot/page limit')
        query = (select(HeadHistoryModel).join(ArtifactModel,
                 ArtifactModel.id == HeadHistoryModel.artifact_id).where(
            HeadHistoryModel.workspace_id == workspace_id,
            HeadHistoryModel.from_catalog_version <= catalog_version,
            or_(HeadHistoryModel.until_catalog_version.is_(None),
                HeadHistoryModel.until_catalog_version > catalog_version),
            HeadHistoryModel.deleted.is_(False), ArtifactModel.deleted.is_(False),
        ))
        if after_id is not None:
            query = query.where(HeadHistoryModel.artifact_id > after_id)
        rows = (await self._uow.session.execute(query.order_by(HeadHistoryModel.artifact_id).limit(limit))).scalars()
        return tuple(Artifact(row.artifact_id, workspace_id, row.path, row.kind,
                              row.revision_id, row.artifact_version) for row in rows)

    async def validate_path(self, workspace_id: str, path: str, *, kind: str,
                            ignore_id: str | None = None):
        logical_path(path)
        segments = path.split('/')
        ancestors = ['/'.join(segments[:index]) for index in range(1, len(segments))]
        query = select(ArtifactModel.id).where(ArtifactModel.workspace_id == workspace_id,
            ArtifactModel.deleted.is_(False), or_(ArtifactModel.path == path,
                (ArtifactModel.path.in_(ancestors) & (ArtifactModel.kind == 'file')),
                ArtifactModel.path.startswith(path + '/', autoescape=True)))
        if ignore_id is not None:
            query = query.where(ArtifactModel.id != ignore_id)
        if (await self._uow.session.execute(query.limit(1))).scalar_one_or_none() is not None:
            raise ArtifactError('ARTIFACT_PATH_CONFLICT', 'Artifact path conflicts with a file or directory')

    async def ensure_parents(self, workspace, path: str):
        segments = path.split('/')
        for index in range(1, len(segments)):
            parent = '/'.join(segments[:index])
            existing = (await self._uow.session.execute(select(ArtifactModel).where(
                ArtifactModel.workspace_id == workspace.id, ArtifactModel.path == parent,
                ArtifactModel.deleted.is_(False)))).scalar_one_or_none()
            if existing is not None:
                if existing.kind != 'directory':
                    raise ArtifactError('ARTIFACT_PATH_CONFLICT', 'A file cannot be a directory')
                continue
            row = ArtifactModel(id=str(uuid4()), workspace_id=workspace.id, path=parent,
                                kind='directory', version=1, deleted=False)
            self._uow.session.add(row)
            await self._uow.session.flush()
            self._uow.session.add(HeadHistoryModel(id=str(uuid4()), workspace_id=workspace.id,
                artifact_id=row.id, from_catalog_version=workspace.catalog_version,
                until_catalog_version=None, path=parent, kind='directory', revision_id=None,
                artifact_version=1, deleted=False))

    async def publish_revision(self, scope: Scope, workspace_id: str, *, path: str,
                               revision: Revision, expected_revision: str | None) -> Artifact:
        logical_path(path)
        workspace = await self.workspace_row(scope, workspace_id, lock=True)
        if workspace.status != 'active':
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Workspace does not accept writes')
        await self.validate_path(workspace_id, path, kind='file', ignore_id=revision.artifact_id)
        existing = (await self._uow.session.execute(select(ArtifactModel).where(
            ArtifactModel.id == revision.artifact_id,
            ArtifactModel.workspace_id == workspace_id,
        ).execution_options(populate_existing=True))).scalar_one_or_none()
        if existing is not None:
            if existing.deleted or existing.kind != 'file' or existing.revision_id != expected_revision:
                raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Artifact revision changed')
            if path != existing.path:
                raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Content write cannot rename an artifact')
        elif expected_revision is not None:
            raise ArtifactError('ARTIFACT_REVISION_CONFLICT', 'Expected artifact revision is unavailable')
        else:
            existing = ArtifactModel(id=revision.artifact_id, workspace_id=workspace_id,
                                     path=path, kind='file', version=1, deleted=False)
            self._uow.session.add(existing)
            await self._uow.session.flush()
        if workspace.used_bytes + workspace.reserved_bytes + revision.size_bytes > workspace.quota_bytes:
            raise ArtifactError('QUOTA_EXCEEDED', 'Artifact workspace storage quota exceeded')
        self._uow.session.add(RevisionModel(**asdict(revision), workspace_id=workspace_id))
        await self._uow.session.flush()
        workspace.used_bytes += revision.size_bytes
        workspace.catalog_version += 1
        await self.ensure_parents(workspace, path)
        existing.revision_id = revision.id
        if expected_revision is not None:
            existing.version += 1
        await self._uow.session.execute(update(HeadHistoryModel).where(
            HeadHistoryModel.workspace_id == workspace_id,
            HeadHistoryModel.artifact_id == existing.id,
            HeadHistoryModel.until_catalog_version.is_(None),
        ).values(until_catalog_version=workspace.catalog_version))
        self._uow.session.add(HeadHistoryModel(
            id=str(uuid4()), workspace_id=workspace_id, artifact_id=existing.id,
            from_catalog_version=workspace.catalog_version,
            until_catalog_version=None, path=existing.path, kind=existing.kind,
            revision_id=revision.id, artifact_version=existing.version, deleted=False,
        ))
        await self._uow.session.flush()
        return artifact_entity(existing)
