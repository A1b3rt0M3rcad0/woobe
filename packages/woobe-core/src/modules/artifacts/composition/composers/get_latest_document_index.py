from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.use_cases.indexes import DocumentIndexUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.indexes import DocumentIndexRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def get_latest_document_index_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    indexes = DocumentIndexRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = DocumentIndexUseCases(indexes, authorization, None)
    return TransactionalHandler(uow, use_case.latest_for_revision)
