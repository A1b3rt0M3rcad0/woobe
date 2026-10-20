from modules.artifacts.application.services.files import FileService
from modules.artifacts.composition.composers.get_file import get_file_composer
from modules.artifacts.composition.composers.list_files import list_files_composer
from modules.artifacts.composition.composers.mutate_file import mutate_file_composer
from modules.artifacts.composition.uploads import build_upload_service, upload_storage


def build_file_service():
    return FileService(get_file_composer(), list_files_composer(), mutate_file_composer(),
                       build_upload_service(), upload_storage)
