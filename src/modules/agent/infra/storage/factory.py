from __future__ import annotations

from modules.agent.application.interfaces.file_storage import FileStorage
from modules.agent.infra.storage.local_file_storage import LocalFileStorage
from modules.agent.infra.storage.s3_file_storage import S3FileStorage
from shared.infra.config import Settings


def create_file_storage(settings: Settings) -> FileStorage:
    driver = settings.storage_driver.strip().lower()
    if driver == "local":
        return LocalFileStorage(settings.upload_local_dir)
    if driver == "s3":
        return S3FileStorage(
            bucket=settings.s3_bucket or "",
            region=settings.s3_region or None,
            prefix=settings.s3_prefix or None,
            endpoint_url=settings.s3_endpoint_url or None,
            force_path_style=settings.s3_force_path_style,
            server_side_encryption=settings.s3_server_side_encryption or None,
        )
    raise ValueError("WOOBE_STORAGE_DRIVER must be one of: local, s3")
