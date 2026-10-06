from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from pathlib import Path
import re
from uuid import uuid4

from modules.package.domain.bundle import MAX_ARCHIVE_BYTES
from modules.package.domain.errors import PackageError

_KEY = re.compile(
    r"^projects/[0-9a-f-]{36}/(?:uploads|exports)/[0-9a-f-]{36}\.tar\.gz$"
)


def validate_storage_key(key):
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        raise PackageError(
            "PACKAGE_STORAGE_INVALID", "Invalid package artifact storage key"
        )
    return key


class LocalPackageArtifactStorage:
    def __init__(self, base_dir):
        self.root = Path(base_dir).absolute() / "packages"
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self.root.is_symlink():
            raise PackageError(
                "PACKAGE_STORAGE_INVALID", "Package artifact root must not be a symlink"
            )

    @contextmanager
    def _parent(self, key, *, create=False):
        parts = validate_storage_key(key).split("/")
        descriptors = []
        try:
            fd = os.open(self.root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            descriptors.append(fd)
            for part in parts[:-1]:
                if create:
                    try:
                        os.mkdir(part, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                fd = os.open(
                    part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd
                )
                descriptors.append(fd)
            yield fd, parts[-1]
        finally:
            for fd in reversed(descriptors):
                os.close(fd)

    def put(self, key, stream):
        digest, size = sha256(), 0
        with self._parent(key, create=True) as (directory, filename):
            temporary = f".{uuid4()}.tmp"
            fd = os.open(
                temporary,
                os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                0o600,
                dir_fd=directory,
            )
            try:
                with os.fdopen(fd, "wb") as output:
                    while block := stream.read(1 << 20):
                        size += len(block)
                        if size > MAX_ARCHIVE_BYTES:
                            raise PackageError(
                                "PACKAGE_LIMIT_EXCEEDED",
                                "Compressed artifact exceeds 128 MiB",
                            )
                        output.write(block)
                        digest.update(block)
                    output.flush()
                    os.fsync(output.fileno())
                # Hard-link publication is atomic and cannot replace an existing artifact.
                os.link(
                    temporary,
                    filename,
                    src_dir_fd=directory,
                    dst_dir_fd=directory,
                    follow_symlinks=False,
                )
                os.fsync(directory)
            finally:
                os.unlink(temporary, dir_fd=directory)
        return {"size_bytes": size, "transport_digest": digest.hexdigest()}

    @contextmanager
    def open(self, key):
        with self._parent(key) as (directory, filename):
            fd = os.open(filename, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=directory)
            with os.fdopen(fd, "rb") as stream:
                yield stream

    def delete(self, key):
        try:
            with self._parent(key) as (directory, filename):
                os.unlink(filename, dir_fd=directory)
        except FileNotFoundError:
            pass


class S3PackageArtifactStorage:
    def __init__(self, settings):
        import boto3
        from botocore.config import Config

        if not settings.s3_bucket:
            raise ValueError("WOOBE_S3_BUCKET is required for package artifact storage")
        self.bucket = settings.s3_bucket
        self.prefix = settings.s3_prefix.strip("/")
        self.encryption = settings.s3_server_side_encryption
        self.client = boto3.client(
            "s3",
            region_name=settings.s3_region,
            endpoint_url=settings.s3_endpoint_url or None,
            config=Config(
                s3={
                    "addressing_style": "path"
                    if settings.s3_force_path_style
                    else "auto"
                }
            ),
        )

    def _key(self, key):
        validate_storage_key(key)
        return "/".join(value for value in (self.prefix, "packages", key) if value)

    def put(self, key, stream):
        # A bounded private spool keeps the SDK's multipart retries off the original stream.
        import tempfile

        digest, size = sha256(), 0
        with tempfile.TemporaryFile() as captured:
            while block := stream.read(1 << 20):
                size += len(block)
                if size > MAX_ARCHIVE_BYTES:
                    raise PackageError(
                        "PACKAGE_LIMIT_EXCEEDED", "Compressed artifact exceeds 128 MiB"
                    )
                digest.update(block)
                captured.write(block)
            captured.seek(0)
            extra = {
                "ContentType": "application/gzip",
                "Metadata": {"sha256": digest.hexdigest()},
            }
            if self.encryption:
                extra["ServerSideEncryption"] = self.encryption
            self.client.upload_fileobj(
                captured, self.bucket, self._key(key), ExtraArgs=extra
            )
        return {"size_bytes": size, "transport_digest": digest.hexdigest()}

    @contextmanager
    def open(self, key):
        response = self.client.get_object(Bucket=self.bucket, Key=self._key(key))
        body = response["Body"]
        try:
            if response["ContentLength"] > MAX_ARCHIVE_BYTES:
                raise PackageError(
                    "PACKAGE_LIMIT_EXCEEDED", "Stored artifact exceeds resource limit"
                )
            yield body
        finally:
            body.close()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=self._key(key))


def build_package_artifact_storage(settings):
    if settings.storage_driver == "local":
        return LocalPackageArtifactStorage(settings.upload_local_dir)
    if settings.storage_driver == "s3":
        return S3PackageArtifactStorage(settings)
    raise ValueError("Unsupported package artifact storage driver")
