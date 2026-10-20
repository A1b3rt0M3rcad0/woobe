from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.use_cases.jobs import ProcessingJobUseCases
from modules.artifacts.application.use_cases.profiles import ProfileUseCases
from modules.artifacts.composition.resources import DATABASE_ENGINE, PROCESSING_REGISTRY, SETTINGS
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def request_processing_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    jobs = ProcessingJobRepository(uow, project_max_jobs=SETTINGS.artifact_processing_project_max_jobs,
        workspace_max_jobs=SETTINGS.artifact_processing_workspace_max_jobs)
    catalog = CatalogRepository(uow)
    profile_store = ProfileRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    profiles = ProfileUseCases(profile_store, authorization, PROCESSING_REGISTRY, CursorCodec(SETTINGS.secret_key.encode()))
    use_case = ProcessingJobUseCases(jobs, catalog, profiles, authorization, PROCESSING_REGISTRY)
    return TransactionalHandler(uow, use_case.request)
