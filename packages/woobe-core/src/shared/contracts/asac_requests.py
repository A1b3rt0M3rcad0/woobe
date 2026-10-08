"""Versioned administrative contracts; IDs and hashes do not grant authority."""
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from shared.contracts.asac import asac_digest

DIGEST = r"^sha256:[a-f0-9]{64}$"
REVISION = r"^rv_[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$"


class StrictASaCRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ASaCRevision(StrictASaCRequest):
    format: Literal["woobe-revision"]
    schema_version: Literal["1.0"]
    revision_id: StrictStr = Field(pattern=REVISION)
    resource_uid: StrictStr
    kind: Literal["Agent", "Network"]
    parents: list[StrictStr] = Field(max_length=64)
    message: StrictStr = Field(min_length=1, max_length=4096)
    artifact_digest: StrictStr = Field(pattern=DIGEST)
    author_artifact_digest: StrictStr | None = Field(default=None, pattern=DIGEST)
    definition_digest: StrictStr = Field(pattern=DIGEST)
    definition_digest_scope: Literal["woobe-portable-definition@1.0"]
    component_digests: dict[StrictStr, StrictStr] = Field(max_length=1024)
    record_digest: StrictStr = Field(pattern=DIGEST)

    @model_validator(mode="after")
    def check_integrity(self):
        import re
        UUID(self.resource_uid)
        if not self.message.strip() or len(self.message.encode()) > 4096:
            raise ValueError("Revision message exceeds canonical bounds")
        if len(set(self.parents)) != len(self.parents) or self.revision_id in self.parents or any(not re.fullmatch(REVISION, parent) for parent in self.parents):
            raise ValueError("Revision parents are invalid")
        for uid, digest in self.component_digests.items():
            UUID(uid)
            if not re.fullmatch(DIGEST, digest):
                raise ValueError("Component digest is invalid")
        document = self.model_dump(exclude_none=True)
        document.pop("record_digest")
        if self.record_digest != asac_digest("record", document):
            raise ValueError("Revision record digest mismatch")
        return self


class OpenASaCDraft(StrictASaCRequest):
    operation_id: UUID
    resource_uid: UUID
    name: StrictStr = Field(min_length=1, max_length=80, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]*$")
    source_export_id: UUID


class SaveASaCDraft(StrictASaCRequest):
    operation_id: UUID
    expected_generation: StrictInt = Field(ge=1)
    upload_id: UUID
    artifact_digest: StrictStr = Field(pattern=DIGEST)


class RegisterASaCRevision(StrictASaCRequest):
    operation_id: UUID
    draft_id: UUID
    expected_generation: StrictInt = Field(ge=1)
    record: ASaCRevision
    component_uids: dict[StrictStr, UUID] = Field(max_length=1024)
    provider_uids: dict[StrictStr, UUID] = Field(default_factory=dict, max_length=1024)
