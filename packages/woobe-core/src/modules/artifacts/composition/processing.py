from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.services.processing_runner import ProcessingRunner
from modules.artifacts.application.use_cases.jobs import ProcessingJobUseCases
from modules.artifacts.application.use_cases.profiles import ProfileUseCases
from modules.artifacts.composition.resources import PROCESSING_REGISTRY
from modules.artifacts.composition.uploads import upload_storage
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from shared.infra.transactional_handler import TransactionalHandler


def _worker_phase(engine, settings, method):
    # The existing Worker process owns this engine's lifecycle. API composers
    # remain zero-argument and use the API composition resource instead.
    uow = ArtifactsUnitOfWork(engine)
    jobs = ProcessingJobRepository(uow, project_max_jobs=settings.artifact_processing_project_max_jobs,
        workspace_max_jobs=settings.artifact_processing_workspace_max_jobs)
    catalog = CatalogRepository(uow)
    profile_store = ProfileRepository(uow)
    grants = GrantRepository(uow)
    authority = ExistingPrincipalAuthority(uow)
    authorization = ArtifactAuthorization(authority, grants)
    profiles = ProfileUseCases(profile_store, authorization, PROCESSING_REGISTRY,
                              CursorCodec(settings.secret_key.encode()))
    use_case = ProcessingJobUseCases(jobs, catalog, profiles, authorization, PROCESSING_REGISTRY)
    return TransactionalHandler(uow, getattr(use_case, method))


def build_processing_runner(engine, settings):
    return ProcessingRunner(_worker_phase(engine, settings, 'deliver'), _worker_phase(engine, settings, 'claim'),
        _worker_phase(engine, settings, 'prepare'), _worker_phase(engine, settings, 'heartbeat'),
        _worker_phase(engine, settings, 'checkpoint'), _worker_phase(engine, settings, 'finish'), upload_storage,
        lease_seconds=settings.artifact_processing_lease_seconds,
        project_limit=settings.artifact_processing_project_slots,
        workspace_limit=min(settings.artifact_processing_workspace_slots, settings.artifact_processing_project_slots))
