"""Resolve and authorize an Agent's logical Workspace binding at Acceptance."""

from uuid import UUID

from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.contracts.api import ArtifactReference
from modules.artifacts.application.contracts.files import ReadFile
from modules.artifacts.application.ports.authorization import GrantReader
from modules.artifacts.composition.resources import DATABASE_ENGINE
from modules.artifacts.domain.models import Action, Environment, RuntimeArtifactBinding, Scope
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.files import FileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


async def resolve_runtime_artifact_workspace_binding(
    *,
    principal,
    project_id: UUID,
    environment: str,
    external_namespace: str,
    external_key: str,
    actions: tuple[str, ...],
    binding_scope: str,
) -> RuntimeArtifactBinding:
    scope = Scope(str(project_id), Environment(environment))
    action_set = frozenset(Action(action) for action in actions)
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    catalog = CatalogRepository(uow)
    grants: GrantReader = GrantRepository(uow)
    authorization = ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants)
    async with uow:
        # Resolve by external identity, never by a caller-supplied technical ID.
        workspace = await catalog.resolve_workspace(scope, external_namespace, external_key)
        for action in sorted(action_set, key=lambda item: item.value):
            await authorization.authorize(principal, scope, workspace.id, action)
        return RuntimeArtifactBinding(
            workspace_id=workspace.id,
            scope=scope,
            catalog_version=workspace.catalog_version,
            actions=action_set,
            binding_scope=binding_scope,
        )


async def validate_runtime_artifact_references(*, principal, binding, references):
    """Recheck current read grants and exact revision availability before model use."""
    if Action.READ not in binding.actions:
        from modules.artifacts.domain.models import ArtifactError

        raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Artifact input requires read capability')
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    grants: GrantReader = GrantRepository(uow)
    authorization = ArtifactAuthorization(ExistingPrincipalAuthority(uow), grants)
    store = FileRepository(uow)
    resolved = []
    async with uow:
        for reference in references:
            reference = ArtifactReference.model_validate(reference)
            await authorization.authorize(
                principal, binding.scope, binding.workspace_id, Action.READ,
                release_actions=binding.actions,
            )
            request = ReadFile(
                principal, binding.scope, binding.workspace_id,
                reference.artifact_id, reference.revision_id,
                catalog_version=binding.catalog_version,
            )
            snapshot = await store.read(request)
            if snapshot.revision is None:
                from modules.artifacts.domain.models import ArtifactError

                raise ArtifactError('SOURCE_UNAVAILABLE', 'Artifact input revision is unavailable')
            resolved.append({
                'artifact_id': reference.artifact_id,
                'revision_id': reference.revision_id,
                'content_type': snapshot.revision.content_type.split(';', 1)[0].strip().lower(),
                'size_bytes': snapshot.revision.size_bytes,
                'source_sha256': snapshot.revision.sha256,
            })
    return tuple(resolved)
