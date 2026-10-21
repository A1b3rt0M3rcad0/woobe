from __future__ import annotations

import logging
import time

from modules.artifacts.composition.uploads import upload_storage
from modules.artifacts.infra.database.lifecycle import ArtifactLifecycleRepository
from shared.observability.metrics import runtime_metrics


logger = logging.getLogger(__name__)


class ArtifactLifecycleWorker:
    """Retryable, bounded object cleanup for retention and explicit deletion."""

    def __init__(self, engine) -> None:
        self._repository = ArtifactLifecycleRepository(engine)
        self._last_staging_sweep = 0.0

    async def _delete(self, target) -> bool:
        started = time.perf_counter()
        succeeded = False
        try:
            storage = upload_storage(target.storage_profile)
            for reference in target.object_refs:
                await storage.delete(reference.key, version_id=reference.version_id)
            succeeded = True
            return True
        except Exception as error:
            # Keep database references intact so a later poll can retry. Avoid
            # putting workspace IDs, paths, or user filenames in worker logs.
            logger.warning(
                "Artifact lifecycle storage cleanup will retry",
                extra={"storage_profile": target.storage_profile, "error_type": type(error).__name__},
            )
            return False
        finally:
            runtime_metrics.observe_artifact_operation(
                operation="retention",
                outcome="success" if succeeded else "error",
                duration_seconds=time.perf_counter() - started,
            )

    async def run(self) -> None:
        if time.monotonic() - self._last_staging_sweep >= 3600:
            self._last_staging_sweep = time.monotonic()
            try:
                local = upload_storage("local")
                cleanup = getattr(local, "cleanup_staging", None)
                if callable(cleanup):
                    await cleanup(older_than_seconds=3600)
            except Exception as error:
                logger.warning(
                    "Artifact local staging cleanup will retry",
                    extra={"error_type": type(error).__name__},
                )
            try:
                s3 = upload_storage("s3")
                abort = getattr(s3, "abort_expired_multipart", None)
                if callable(abort):
                    async def is_active(key, upload_id):
                        try:
                            return await self._repository.multipart_upload_active(key, upload_id)
                        except Exception as error:
                            logger.warning(
                                "Artifact multipart cleanup could not check its database fence",
                                extra={"error_type": type(error).__name__},
                            )
                            return True

                    await abort(prefix="projects", older_than_seconds=3600, is_active=is_active)
            except Exception as error:
                logger.warning(
                    "Artifact S3 multipart cleanup will retry",
                    extra={"error_type": type(error).__name__},
                )

        await self._repository.mark_retention_expired(limit=50)

        for target in await self._repository.expired_upload_cleanup(limit=50):
            if await self._delete(target):
                await self._repository.finish_upload_cleanup(target)

        for target in await self._repository.due_revision_cleanup(limit=20):
            if await self._delete(target):
                await self._repository.finish_revision_cleanup(target)

        for target in await self._repository.pending_workspace_cleanup(limit=10):
            if await self._delete(target):
                await self._repository.finish_workspace_cleanup(target)
