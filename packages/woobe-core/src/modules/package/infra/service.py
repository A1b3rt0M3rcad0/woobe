from __future__ import annotations

from hashlib import sha256
from uuid import UUID

from modules.package.domain.bundle import (
    MAX_ARCHIVE_BYTES,
    MAX_BUNDLE_BYTES,
    MAX_FILES,
    MAX_FILE_BYTES,
)
from modules.package.domain.operations import operation_status
from shared.infra.admin_idempotency import principal_identity


class PackageService:
    """Transport-independent facade over Package-owned durable repositories."""

    def __init__(self, artifacts, plans, operations, inspector):
        self.artifacts, self.plans, self.operations, self.inspector = (
            artifacts,
            plans,
            operations,
            inspector,
        )

    async def capabilities(self, *, project_id, principal):
        await self.artifacts.authorize_read(project_id, principal)
        capabilities = await self.inspector.capabilities()
        fingerprint = sha256(
            b"woobe-package-principal@1.0\n" + principal_identity(principal).encode()
        ).hexdigest()
        return {
            **capabilities,
            "supported_operations": [
                "upload",
                "plan",
                "status",
                "lookup",
                "resume",
                "cancel",
            ],
            "principal_fingerprint": fingerprint,
            "formats": ["directory", "tar.gz"],
            "limits": {
                "files": MAX_FILES,
                "file_bytes": MAX_FILE_BYTES,
                "bundle_bytes": MAX_BUNDLE_BYTES,
                "archive_bytes": MAX_ARCHIVE_BYTES,
            },
        }

    async def plan(self, *, project_id, principal, request, api_origin):
        return await self.plans.create(
            project_id=project_id,
            principal=principal,
            upload_id=UUID(request.upload_id),
            artifact_digest=request.artifact_digest,
            bindings=request.bindings.model_dump(mode="json", exclude_none=True),
            lifecycle=request.lifecycle,
            release_notes=request.release_notes,
            reason=request.reason,
            api_origin=api_origin,
        )

    async def status(self, *, project_id, principal, operation_id):
        return operation_status(
            await self.operations.get(
                project_id=project_id, principal=principal, operation_id=operation_id
            )
        )

    async def lookup(self, *, project_id, principal, key):
        return operation_status(
            await self.operations.lookup(
                project_id=project_id, principal=principal, key=key
            )
        )

    async def cancel(self, *, project_id, principal, operation_id):
        return operation_status(
            await self.operations.cancel(
                project_id=project_id, principal=principal, operation_id=operation_id
            )
        )

    async def resume(self, *, project_id, principal, operation_id, expected_revision):
        return operation_status(
            await self.operations.resume(
                project_id=project_id,
                principal=principal,
                operation_id=operation_id,
                expected_revision=expected_revision,
            )
        )
