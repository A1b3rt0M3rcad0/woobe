from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.workspaces import WorkspaceUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def list_workspaces_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    catalog = CatalogRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = WorkspaceUseCases(catalog, grants, authorization, CursorCodec(SETTINGS.secret_key.encode()))
    return TransactionalHandler(uow, use_case.list)
