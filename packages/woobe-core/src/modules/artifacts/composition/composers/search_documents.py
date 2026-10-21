from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.search import ArtifactSearchUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.artifacts.composition.run_sources import record_run_source
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.search import ArtifactSearchRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def search_documents_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    store = ArtifactSearchRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = ArtifactSearchUseCases(store, authorization, CursorCodec(SETTINGS.secret_key.encode()),
        record_run_source)
    return TransactionalHandler(uow, use_case.search)
