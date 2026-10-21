from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.indexes import DocumentIndexUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.indexes import DocumentIndexRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def list_document_nodes_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    files = DocumentIndexRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = DocumentIndexUseCases(files, authorization, CursorCodec(SETTINGS.secret_key.encode()))
    return TransactionalHandler(uow, use_case.nodes)
