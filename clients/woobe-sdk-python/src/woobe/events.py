from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from woobe.artifacts import ArtifactOutput, ArtifactTransfer
from woobe.errors import WoobeProtocolError

RUNTIME_STREAM_PROTOCOL_VERSION = 2
RunKind = Literal["AGENT", "NETWORK"]


class WoobeEvent(BaseModel):
    """Canonical semantic event emitted by the Woobe Runtime stream protocol v2."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    protocol_version: Literal[2] = RUNTIME_STREAM_PROTOCOL_VERSION
    event_id: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    session_id: str = Field(min_length=1)
    run_kind: RunKind
    sequence: int = Field(ge=0, strict=True)
    type: str = Field(min_length=1)
    occurred_at: datetime
    payload: dict[str, Any]

    def artifact_available(self) -> ArtifactOutput | None:
        """Return metadata from an artifact.available event without fetching bytes."""
        if self.type not in {"artifact.available", "artifact_available"}:
            return None
        raw = dict(self.payload)
        if "ref" not in raw:
            raw["ref"] = {
                "artifact_id": raw.get("artifact_id"),
                "revision_id": raw.get("revision_id"),
            }
        raw.setdefault("run_id", self.run_id)
        raw["schema_version"] = "1"
        try:
            return ArtifactOutput.model_validate(raw)
        except ValueError as exc:
            raise WoobeProtocolError(
                "artifact.available lacks a valid exact revision receipt"
            ) from exc

    def artifact_transfer(self) -> ArtifactTransfer | None:
        """Return a redacted transfer receipt from a Runtime event, if present."""
        if self.type != "artifact_transfer" and not self.type.startswith("artifact.transfer."):
            return None
        try:
            receipt = ArtifactTransfer.model_validate(self.payload)
        except ValueError as exc:
            raise WoobeProtocolError(
                "Artifact transfer event lacks operation identity or state"
            ) from exc
        if not receipt.operation_id or not receipt.state:
            raise WoobeProtocolError("Artifact transfer event lacks operation identity or state")
        return receipt
