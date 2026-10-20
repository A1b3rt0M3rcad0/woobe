from modules.artifacts.application.services.representations import RepresentationService
from modules.artifacts.composition.composers.get_representation import get_representation_composer
from modules.artifacts.composition.composers.list_representation_entries import list_representation_entries_composer
from modules.artifacts.composition.composers.resolve_source import resolve_source_composer
from modules.artifacts.composition.uploads import build_upload_service, upload_storage


def build_representation_service():
    return RepresentationService(get_representation_composer(), list_representation_entries_composer(),
        resolve_source_composer(), upload_storage, build_upload_service())
