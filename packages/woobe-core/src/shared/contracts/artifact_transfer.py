"""Runtime-only streaming source for a governed Artifact transfer."""

from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(frozen=True)
class ArtifactTransferSource:
    artifact_id: str
    revision_id: str
    path: str
    content_type: str
    size_bytes: int
    sha256: str
    content: AsyncIterator[bytes] | None = None
    temporary_url: str | None = None
    expires_in_seconds: int | None = None
