from modules.artifacts.composition.document_model_usage import model_usage_delivery
from sqlalchemy.ext.asyncio import async_sessionmaker
from modules.artifacts.composition.document_model_gateway import GovernedDocumentModelGateway
from modules.artifacts.infra.database.document_model_calls import DocumentModelCallRepository
from modules.artifacts.composition.document_model_bindings import DocumentModelBindingRepository
from modules.artifacts.application.authorization import ArtifactAuthorization
from modules.artifacts.application.cursors import CursorCodec
from modules.artifacts.application.services.processing_runner import ProcessingRunner
from modules.artifacts.application.services.document_pipeline import DocumentPipeline
from modules.artifacts.infra.processing.native_text import NativeTextProcessor
from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor
from modules.artifacts.infra.processing.docling_native import DoclingNativeProcessor
from modules.artifacts.infra.processing.native_document import NativeDocumentProcessor
from modules.artifacts.infra.indexers.pageindex_runner import PageIndexRunner
from shared.infra.object_storage.io import run_blocking
from modules.artifacts.application.use_cases.jobs import ProcessingJobUseCases
from modules.artifacts.application.use_cases.profiles import ProfileUseCases
from modules.artifacts.composition.resources import PROCESSING_REGISTRY
from modules.artifacts.composition.uploads import upload_storage
from modules.artifacts.infra.database.authorization import ExistingPrincipalAuthority, GrantRepository
from modules.artifacts.infra.database.catalog import CatalogRepository
from modules.artifacts.infra.database.jobs import ProcessingJobRepository
from modules.artifacts.infra.database.profiles import ProfileRepository
from modules.artifacts.infra.database.representations import RepresentationRepository
from modules.artifacts.infra.database.indexes import DocumentIndexRepository
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
    use_case = ProcessingJobUseCases(jobs, catalog, profiles, authorization, PROCESSING_REGISTRY, RepresentationRepository(uow), DocumentIndexRepository(uow),
        model_bindings=DocumentModelBindingRepository(uow), model_calls=DocumentModelCallRepository(uow))
    return TransactionalHandler(uow, getattr(use_case, method))


def build_processing_runner(engine, settings):
    phases = {name: _worker_phase(engine, settings, name) for name in (
        'reserve_output', 'record_output', 'prepare_bundle', 'metadata_bundle', 'seal_bundle',
        'prepare_index', 'metadata_index', 'seal_index')}

    model_phases = {name: _worker_phase(engine, settings, name) for name in (
        'admit_model', 'model_configuration', 'dispatch_model', 'observe_model')}
    model_gateway = GovernedDocumentModelGateway(model_phases,
        session_factory=async_sessionmaker(engine, expire_on_commit=False), encryption_key=settings.encryption_key)

    async def publication_phase(name, request):
        return await phases[name](request)

    return ProcessingRunner(model_usage_delivery(engine, _worker_phase(engine, settings, 'deliver')), _worker_phase(engine, settings, 'claim'),
        _worker_phase(engine, settings, 'prepare'), _worker_phase(engine, settings, 'heartbeat'),
        _worker_phase(engine, settings, 'checkpoint'), _worker_phase(engine, settings, 'finish'), upload_storage,
        publication_phase=publication_phase,
        pipeline=DocumentPipeline({('native-text', '1'): NativeTextProcessor(),
                                   ('native-pdf', '1'): NativePdfProcessor(),
                                   ('native-document', '1'): NativeDocumentProcessor(
                                       ocr_data_dir=settings.artifact_ocr_data_dir,
                                       tesseract_executable=settings.artifact_tesseract_executable),
                                   ('docling-native', '2.140.0'): DoclingNativeProcessor(
                                       memory_bytes=settings.artifact_docling_memory_mib * 1_048_576,
                                       threads=settings.artifact_docling_threads)}, run_blocking, model_gateway=model_gateway,
            indexers={(PageIndexRunner.name, PageIndexRunner.version): PageIndexRunner()}),
        lease_seconds=settings.artifact_processing_lease_seconds,
        project_limit=settings.artifact_processing_project_slots,
        workspace_limit=min(settings.artifact_processing_workspace_slots, settings.artifact_processing_project_slots))
