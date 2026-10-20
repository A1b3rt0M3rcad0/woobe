from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.profiles import ProfileUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, PROCESSING_REGISTRY, SETTINGS
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def create_processing_profile_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    profiles = ProfileRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    use_case = ProfileUseCases(profiles, authorization, PROCESSING_REGISTRY, CursorCodec(SETTINGS.secret_key.encode()))
    return TransactionalHandler(uow, use_case.create)
