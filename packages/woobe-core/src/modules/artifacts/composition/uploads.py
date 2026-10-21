from functools import lru_cache

from modules.artifacts.application.services.uploads import UploadService
from modules.artifacts.composition.storage import build_artifact_storage
from modules.artifacts.composition.composers.begin_upload import begin_upload_composer
from modules.artifacts.composition.composers.get_upload import get_upload_composer
from modules.artifacts.composition.composers.admit_upload import admit_upload_composer
from modules.artifacts.composition.composers.record_upload import record_upload_composer
from modules.artifacts.composition.composers.verify_upload import verify_upload_composer
from modules.artifacts.composition.composers.commit_upload import commit_upload_composer
from modules.artifacts.composition.composers.abort_upload import abort_upload_composer


@lru_cache(maxsize=2)
def upload_storage(profile):
    return build_artifact_storage(profile)


def build_upload_service():
    return UploadService(begin_upload_composer(), get_upload_composer(), admit_upload_composer(),
        record_upload_composer(), verify_upload_composer(), commit_upload_composer(),
        abort_upload_composer(), upload_storage)
