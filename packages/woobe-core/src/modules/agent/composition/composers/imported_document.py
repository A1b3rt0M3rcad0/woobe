from modules.agent.application.use_cases.prepare_imported_document import (
    PrepareImportedDocumentUseCase,
)
from modules.agent.composition.resources import FILE_STORAGE, SETTINGS


def build_imported_document_preparation() -> PrepareImportedDocumentUseCase:
    return PrepareImportedDocumentUseCase(FILE_STORAGE, SETTINGS)
