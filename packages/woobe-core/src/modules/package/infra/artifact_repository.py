from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
import tempfile
from uuid import uuid4

from modules.package.domain.errors import PackageError
from modules.package.infra.bundles import receive_archive
from modules.package.infra.models import PackageUploadModel
from modules.package.infra.operation_repository import as_utc
from modules.package.infra.receipts import authorize_phase
from shared.infra.admin_idempotency import principal_identity


def upload_status(record):
    return {
        "upload_id": str(record.id),
        "project_id": str(record.project_id),
        "package_schema_version": "1.0",
        "artifact_digest": record.artifact_digest,
        "size_bytes": record.size_bytes,
        "inventory": record.inventory,
        "expires_at": record.expires_at.isoformat(),
    }


class PackageArtifactRepository:
    """Owns durable captures, with no SQL transaction open during artifact I/O."""

    def __init__(self, session_factory, storage, *, lifetime_seconds=86_400):
        self.session_factory, self.storage = session_factory, storage
        self.lifetime_seconds = lifetime_seconds

    async def authorize_read(self, project_id, principal):
        async with self.session_factory() as session:
            await authorize_phase(session, principal, project_id, "project:read")

    def _capture_upload(self, key, stream, locked):
        with receive_archive(stream, locked=locked) as bundle:
            with tempfile.TemporaryFile() as archive:
                bundle.archive(archive, include_lock=True)
                archive.seek(0)
                stored = self.storage.put(key, archive)
            return (
                bundle.graph.manifest,
                bundle.inventory,
                bundle.artifact_digest,
                stored,
            )

    async def upload(self, *, project_id, principal, stream, locked=False):
        await self.authorize_read(project_id, principal)
        identifier = uuid4()
        key = f"projects/{project_id}/uploads/{identifier}.tar.gz"
        manifest, inventory, digest, stored = await asyncio.to_thread(
            self._capture_upload, key, stream, locked
        )
        record = PackageUploadModel(
            id=identifier,
            project_id=project_id,
            actor=principal_identity(principal),
            artifact_digest=digest,
            storage_key=key,
            manifest=manifest,
            inventory=inventory,
            size_bytes=stored["size_bytes"],
            expires_at=datetime.now(UTC) + timedelta(seconds=self.lifetime_seconds),
        )
        # Recheck authority after potentially long decompression/storage. A failure
        # with uncertain commit outcome retains the random artifact for recovery;
        # deleting it here could corrupt an upload whose COMMIT reached the DB.
        async with self.session_factory.begin() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            session.add(record)
            await session.flush()
        return upload_status(record)

    async def get_record(
        self, *, project_id, principal, upload_id, allow_expired=False
    ):
        async with self.session_factory() as session:
            await authorize_phase(session, principal, project_id, "project:read")
            record = await session.get(PackageUploadModel, upload_id)
            if (
                record is None
                or record.project_id != project_id
                or record.actor != principal_identity(principal)
            ):
                raise PackageError(
                    "PACKAGE_UPLOAD_NOT_FOUND", "Uploaded package is unavailable"
                )
            if not allow_expired and as_utc(record.expires_at) <= datetime.now(UTC):
                raise PackageError(
                    "PACKAGE_UPLOAD_EXPIRED", "Uploaded package has expired"
                )
            return record

    async def get(self, **kwargs):
        return upload_status(await self.get_record(**kwargs))

    def capture_record(self, record):
        with self.storage.open(record.storage_key) as stream:
            bundle = receive_archive(stream, locked=True)
        if (
            bundle.artifact_digest != record.artifact_digest
            or bundle.inventory != record.inventory
        ):
            bundle.close()
            raise PackageError(
                "PACKAGE_ARTIFACT_CHANGED",
                "Stored package differs from its accepted inventory",
            )
        return bundle
