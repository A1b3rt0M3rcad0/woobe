from pathlib import Path

from modules.artifacts.composition.resources import SETTINGS
from shared.contracts.object_storage import ObjectStorageError
from shared.infra.object_storage.local import LocalObjectStorage


def build_artifact_storage():
    if SETTINGS.storage_driver.strip().lower() != 'local':
        raise ObjectStorageError('unavailable', 'Requested artifact storage adapter is unavailable')
    return LocalObjectStorage(Path(SETTINGS.upload_local_dir) / 'artifacts')
