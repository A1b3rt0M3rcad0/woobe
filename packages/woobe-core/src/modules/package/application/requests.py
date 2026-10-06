from typing import Literal

from pydantic import Field, model_validator

from modules.package.application.dtos import StrictDTO, ImportBindingsV1

UUID_PATTERN = (
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
DIGEST_PATTERN = r"^[a-f0-9]{64}$"


class PlanPackageRequest(StrictDTO):
    mode: Literal["create"] = "create"
    upload_id: str = Field(pattern=UUID_PATTERN)
    artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    bindings: ImportBindingsV1
    lifecycle: Literal["draft", "staging", "release", "production"] = "draft"
    release_notes: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class ApplyPackageRequest(StrictDTO):
    plan_id: str = Field(pattern=UUID_PATTERN)
    plan_digest: str = Field(pattern=DIGEST_PATTERN)
    upload_id: str = Field(pattern=UUID_PATTERN)
    artifact_digest: str = Field(pattern=DIGEST_PATTERN)
    bindings: ImportBindingsV1
    protected_bindings: dict[str, str] = Field(default_factory=dict, max_length=1024)
    lifecycle: Literal["draft", "staging", "release", "production"] = "draft"
    release_notes: str | None = Field(default=None, max_length=4000)
    reason: str | None = Field(default=None, max_length=1000)


class LookupPackageOperationRequest(StrictDTO):
    idempotency_key: str = Field(
        min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_.:-]+$"
    )


class ResumePackageOperationRequest(StrictDTO):
    expected_revision: int = Field(ge=1)


class ExportPackageRequest(StrictDTO):
    kind: Literal["Agent", "Network"]
    target_id: str = Field(pattern=UUID_PATTERN)
    source: Literal["draft", "staging", "release", "production"] | None = None
    snapshot_id: str | None = Field(default=None, pattern=UUID_PATTERN)
    knowledge: Literal["portable", "binding"] = "portable"
    name: str = Field(min_length=1, max_length=255)
    version: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def exclusive_source(self):
        if (self.source is None) == (self.snapshot_id is None):
            raise ValueError("Export requires exactly one source selector")
        return self
