from modules.artifacts.application.use_cases.render_representation_page import RenderRepresentationPageUseCase
from modules.artifacts.composition.files import build_file_service
from modules.artifacts.composition.representations import build_representation_service
from modules.artifacts.composition.resources import DATABASE_ENGINE
from modules.artifacts.infra.database.unit_of_work import ArtifactsUnitOfWork
from modules.artifacts.infra.processing.native_pdf import NativePdfProcessor
from shared.infra.transactional_handler import TransactionalHandler


def render_representation_page_composer() -> TransactionalHandler:
    uow = ArtifactsUnitOfWork(DATABASE_ENGINE)
    use_case = RenderRepresentationPageUseCase(
        build_representation_service(),
        build_file_service(),
        NativePdfProcessor(),
    )
    return TransactionalHandler(uow, use_case.execute)
