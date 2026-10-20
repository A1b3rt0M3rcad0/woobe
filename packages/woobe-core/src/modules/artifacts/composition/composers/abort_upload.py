from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.use_cases.uploads import UploadUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.uploads import UploadRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def abort_upload_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    uploads = UploadRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = UploadUseCases(uploads, authorization, max_upload_bytes=SETTINGS.upload_max_mb * 1024 * 1024)
    return TransactionalHandler(uow, use_case.abort)
