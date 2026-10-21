from modules.artifacts.application.authorization import ArtifactAuthorization, principal_identity
from modules.artifacts.application.contracts.api import CursorEnvelope
from modules.artifacts.application.contracts.processing import ProcessingRecipe, ProfileView
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.ports.profiles import ProfileStore
from modules.artifacts.application.processing_registry import ProcessingRegistry
from modules.artifacts.domain.models import Action, ArtifactError, Page, opaque_id
from shared.security.principal import ProjectApiPrincipal


class ProfileUseCases:
    def __init__(self, store: ProfileStore, authorization: ArtifactAuthorization,
                 registry: ProcessingRegistry, cursors: CursorCodec):
        self._store, self._authorization = store, authorization
        self._registry, self._cursors = registry, cursors

    def _view(self, record):
        try:
            readiness = self._registry.readiness(record['recipe'])
        except (ArtifactError, ValueError):
            # Persisted recipes remain readable after an optional plugin is
            # removed or its supported limits change. They are not runnable.
            readiness = {'ready': False, 'diagnostics': ('registered_recipe_unavailable',)}
        return ProfileView(**record, ready=readiness['ready'], diagnostics=readiness['diagnostics'])

    async def _admin(self, request):
        await self._authorization.require_project(request.principal, request.scope, Action.MANAGE)
        if isinstance(request.principal, ProjectApiPrincipal):
            raise ArtifactError('ARTIFACT_ACCESS_DENIED', 'Runtime credentials cannot create processing profiles')

    async def create(self, request):
        await self._admin(request)
        recipe = self._registry.normalize(request.definition.recipe)
        definition = request.definition.model_copy(update={'recipe': recipe})
        return self._view(await self._store.create(request.scope, definition))

    async def get(self, request):
        await self._authorization.require_project(request.principal, request.scope, Action.READ)
        opaque_id(request.profile_id)
        if type(request.revision) is not int or not 1 <= request.revision <= 9_223_372_036_854_775_807:
            raise ValueError('Invalid processing profile revision')
        return self._view(await self._store.get(request.scope, request.profile_id, request.revision))

    async def page(self, request):
        await self._authorization.require_project(request.principal, request.scope, Action.READ)
        if not 1 <= request.limit <= 200:
            raise ArtifactError('ARTIFACT_LIMIT_EXCEEDED', 'Profile page limit must be between 1 and 200')
        fingerprint = self._cursors.fingerprint({'project': request.scope.project_id,
            'environment': request.scope.environment.value, 'principal': principal_identity(request.principal), 'purpose': 'profiles'})
        cursor = self._cursors.decode(request.cursor, fingerprint=fingerprint, purpose='profiles') if request.cursor else None
        rows = await self._store.page(request.scope, after=cursor.last_id if cursor else None, limit=request.limit + 1)
        more = len(rows) > request.limit
        items = tuple(self._view(record) for record in rows[:request.limit])
        token = self._cursors.encode(CursorEnvelope(scope_fingerprint=fingerprint,
            last_id=items[-1].id, catalog_version=0, purpose='profiles')) if more else None
        return Page(items, more, token)

    async def bind(self, request):
        await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.MANAGE)
        definition = request.definition
        if definition.profile_id is not None:
            await self._store.get(request.scope, definition.profile_id, definition.profile_revision)
        return await self._store.bind(request.scope, request.workspace_id, definition)

    async def select(self, request):
        workspace = await self._authorization.authorize(request.principal, request.scope, request.workspace_id, Action.PROCESS)
        if (request.profile_id is None) != (request.profile_revision is None):
            raise ValueError('Explicit profile selection requires identity and revision')
        selected = request.profile_id or workspace.default_profile_id
        revision = request.profile_revision if request.profile_id else workspace.default_profile_revision
        if selected is None:
            recipe = ProcessingRecipe()
            return {'profile': None, 'recipe': recipe, 'ready': True, 'diagnostics': (),
                    'fingerprint': recipe.fingerprint(), 'mode': 'store_only'}
        profile = self._view(await self._store.get(request.scope, selected, revision))
        return {'profile': profile, 'recipe': profile.recipe, 'ready': profile.ready,
                'diagnostics': profile.diagnostics, 'fingerprint': profile.fingerprint, 'mode': profile.recipe.mode}
