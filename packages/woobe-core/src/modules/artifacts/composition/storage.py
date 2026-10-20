from pathlib import Path

from modules.artifacts.composition.resources import SETTINGS
from shared.contracts.object_storage import ObjectStorageError
from shared.infra.object_storage.local import LocalObjectStorage
from shared.infra.object_storage.s3_factory import create_s3_object_storage


def build_artifact_storage(profile: str | None = None):
    selected = profile or SETTINGS.storage_driver.strip().lower()
    if selected == 'local':
        return LocalObjectStorage(Path(SETTINGS.upload_local_dir) / 'artifacts')
    if selected == 's3' and SETTINGS.s3_bucket:
        prefix = '/'.join(part for part in (SETTINGS.s3_prefix.strip('/'), 'artifacts') if part)
        return create_s3_object_storage(bucket=SETTINGS.s3_bucket, region=SETTINGS.s3_region,
            prefix=prefix, endpoint_url=SETTINGS.s3_endpoint_url,
            force_path_style=SETTINGS.s3_force_path_style,
            server_side_encryption=SETTINGS.s3_server_side_encryption)
    raise ObjectStorageError('unavailable', 'Requested artifact storage adapter is unavailable')
