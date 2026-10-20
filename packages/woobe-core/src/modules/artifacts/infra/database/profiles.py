from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import ArtifactError
from modules.artifacts.infra.database.catalog import CatalogRepository, workspace_entity
from modules.artifacts.infra.database.models import ProcessingProfileModel
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork


def profile_record(row):
    return {'id': row.id, 'revision': row.revision, 'project_id': str(row.project_id),
            'environment': row.environment, 'fingerprint': row.fingerprint,
            'recipe': ProcessingRecipe.model_validate(row.recipe)}


class ProfileRepository:
    def __init__(self, uow: ArtifactsUnitOfWork):
        self._uow = uow
        self._catalog = CatalogRepository(uow)

    @staticmethod
    def _scope(scope):
        return (ProcessingProfileModel.project_id == UUID(scope.project_id),
                ProcessingProfileModel.environment == scope.environment.value)

    async def create(self, scope, definition):
        fingerprint = definition.recipe.fingerprint()
        await self._uow.session.execute(insert(ProcessingProfileModel).values(
            project_id=UUID(scope.project_id), environment=scope.environment.value,
            id=definition.id, revision=definition.revision, fingerprint=fingerprint,
            recipe=definition.recipe.model_dump(mode='json'),
        ).on_conflict_do_nothing(index_elements=['project_id', 'environment', 'id', 'revision']))
        current = await self.get(scope, definition.id, definition.revision)
        if current['fingerprint'] != fingerprint:
            raise ArtifactError('ARTIFACT_IDEMPOTENCY_CONFLICT', 'Processing profile revision is immutable')
        return current

    async def get(self, scope, profile_id, revision):
        row = (await self._uow.session.execute(select(ProcessingProfileModel).where(
            *self._scope(scope), ProcessingProfileModel.id == profile_id,
            ProcessingProfileModel.revision == revision,
        ))).scalar_one_or_none()
        if row is None:
            raise ArtifactError('SOURCE_UNAVAILABLE', 'Processing profile revision is unavailable')
        return profile_record(row)

    async def page(self, scope, *, after, limit):
        # One latest revision per profile identity; execution/default bindings
        # always name an exact revision, never a moving latest alias.
        query = select(ProcessingProfileModel).where(*self._scope(scope))
        if after is not None:
            query = query.where(ProcessingProfileModel.id > after)
        query = query.distinct(ProcessingProfileModel.id).order_by(
            ProcessingProfileModel.id, ProcessingProfileModel.revision.desc()).limit(limit)
        return tuple(profile_record(row) for row in (await self._uow.session.execute(query)).scalars())

    async def bind(self, scope, workspace_id, definition):
        workspace = await self._catalog.workspace_row(scope, workspace_id, lock=True)
        if workspace.version != definition.expected_version:
            raise ArtifactError('WORKSPACE_REVISION_CONFLICT', 'Workspace version changed')
        if workspace.status not in {'active', 'archived'}:
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Workspace does not accept profile changes')
        if definition.profile_id is not None:
            await self.get(scope, definition.profile_id, definition.profile_revision)
        selected = (definition.profile_id, definition.profile_revision)
        if selected != (workspace.default_profile_id, workspace.default_profile_revision):
            workspace.default_profile_id, workspace.default_profile_revision = selected
            workspace.version += 1
        await self._uow.session.flush()
        return workspace_entity(workspace)
