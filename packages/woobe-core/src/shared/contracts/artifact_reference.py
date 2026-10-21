"""Stable exact-revision Artifact reference shared across bounded contexts."""

from pydantic import BaseModel, ConfigDict, Field


_IDENTIFIER_PATTERN = r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}"


class ArtifactReference(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    artifact_id: str = Field(pattern=f"^{_IDENTIFIER_PATTERN}$")
    revision_id: str = Field(pattern=f"^{_IDENTIFIER_PATTERN}$")
