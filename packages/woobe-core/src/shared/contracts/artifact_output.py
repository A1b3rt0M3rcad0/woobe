"""Durable, provider-neutral references to files published by a Run."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from shared.contracts.artifact_reference import ArtifactReference


class ArtifactOutput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["1"] = "1"
    ref: ArtifactReference
    path: str = Field(min_length=1, max_length=1024)
    content_type: str = Field(min_length=3, max_length=255)
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: Literal["available"] = "available"
    run_id: str | None = Field(default=None, min_length=1, max_length=128)
    node_id: str | None = Field(default=None, min_length=1, max_length=128)
    source_refs: tuple[dict[str, Any], ...] = ()
