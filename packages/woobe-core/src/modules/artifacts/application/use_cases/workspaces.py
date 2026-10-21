import hashlib
import json
from datetime import UTC, datetime
from uuid import uuid4

from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.workspaces import (
    ChangeWorkspace, CreateWorkspace, CreateWorkspaceGrant, ListWorkspaces,
    ReadWorkspace, ResolveWorkspace, RevokeWorkspaceGrant,
)
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.ports.workspaces import GrantWriter, WorkspaceStore
from modules.artifacts.domain.models import Action, ArtifactError, Page, Workspace, WorkspaceGrant
from shared.security.principal import ProjectApiPrincipal


class WorkspaceUseCases:
    def __init__(self, store: WorkspaceStore, grants: GrantWriter,
                 authorization: ArtifactAuthorization, cursors: CursorCodec,
                 *, storage_profiles: frozenset[str] = frozenset({'local'})):
        self._store = store
        self._grants = grants
        self._authorization = authorization
        self._cursors = cursors
        self._storage_profiles = storage_profiles

    async def create(self, request: CreateWorkspace) -> Workspace:
        definition = request.definition
        if definition.environment != request.scope.environment:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact access is denied')
        await self._authorization.authorize_namespace(request.principal, request.scope,
                                                      definition.external_namespace, Action.MANAGE)
        if definition.storage_profile not in self._storage_profiles:
            raise ArtifactError('ARTIFACT_STORAGE_UNAVAILABLE', 'Requested storage profile is unavailable')
        candidate = Workspace(
            id=str(uuid4()), scope=request.scope, external_namespace=definition.external_namespace,
            external_key=definition.external_key, name=definition.name,
            storage_profile=definition.storage_profile, quota_bytes=definition.quota_bytes,
            retention_days=definition.retention_days, labels=tuple(sorted(definition.labels.items())),
        )
        fingerprint = hashlib.sha256(json.dumps(definition.model_dump(mode='json'),
            sort_keys=True, separators=(',', ':')).encode()).hexdigest()
        workspace, created = await self._store.provision_workspace(candidate, fingerprint)
        if created and not isinstance(request.principal, ProjectApiPrincipal):
            await self._grants.add(WorkspaceGrant(
                id=str(uuid4()), principal_id=principal_identity(request.principal), scope=request.scope,
                actions=frozenset(Action), workspace_id=workspace.id,
            ))
        if not created:
            await self._authorization.authorize(request.principal, request.scope, workspace.id, Action.MANAGE)
        return workspace

    async def get(self, request: ReadWorkspace) -> Workspace:
        return await self._authorization.authorize(request.principal, request.scope,
                                                  request.workspace_id, Action.READ)

    async def resolve(self, request: ResolveWorkspace) -> Workspace:
        await self._authorization.require_project(request.principal, request.scope, Action.READ)
        workspace = await self._store.resolve_workspace(request.scope, request.external_namespace,
                                                        request.external_key)
        return await self._authorization.authorize(request.principal, request.scope, workspace.id, Action.READ)

    async def list(self, request: ListWorkspaces) -> Page[Workspace]:
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Workspace page limit must be between 1 and 200')
        await self._authorization.require_project(request.principal, request.scope, Action.READ)
        subject = principal_identity(request.principal)
        fingerprint = self._cursors.fingerprint({
            'project': request.scope.project_id, 'environment': request.scope.environment.value,
            'principal': subject, 'namespace': request.external_namespace, 'purpose': 'workspaces',
        })
        after = self._cursors.decode(request.cursor, fingerprint=fingerprint,
                                     purpose='workspaces').last_id if request.cursor else None
        rows = await self._store.accessible_workspaces(request.scope, subject,
            limit=request.limit + 1, after_id=after, namespace=request.external_namespace)
        more = len(rows) > request.limit
        items = rows[:request.limit]
        cursor = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint,
            last_id=items[-1].id, catalog_version=0, purpose='workspaces')) if more else None
        return Page(items, has_more=more, next_cursor=cursor)

    async def update(self, request: ChangeWorkspace) -> Workspace:
        await self._authorization.authorize(request.principal, request.scope,
                                             request.workspace_id, Action.MANAGE)
        return await self._store.update_workspace(request.scope, request.workspace_id,
                                                   **request.definition.model_dump())

    async def grant(self, request: CreateWorkspaceGrant) -> WorkspaceGrant:
        await self._authorization.require_project(request.principal, request.scope, Action.MANAGE)
        if isinstance(request.principal, ProjectApiPrincipal):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Runtime credentials cannot delegate grants')
        grant = WorkspaceGrant(id=str(uuid4()), principal_id=request.subject_id, scope=request.scope,
            actions=request.actions, workspace_id=request.workspace_id,
            external_namespace=request.external_namespace, expires_at=request.expires_at)
        if grant.expires_at is not None and grant.expires_at <= datetime.now(UTC):
            raise ValueError('New grant expiration must be in the future')
        await self._grants.add(grant)
        return grant

    async def revoke_grant(self, request: RevokeWorkspaceGrant):
        await self._authorization.require_project(request.principal, request.scope, Action.MANAGE)
        if isinstance(request.principal, ProjectApiPrincipal):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Runtime credentials cannot revoke grants')
        await self._grants.revoke(request.scope, request.grant_id)
