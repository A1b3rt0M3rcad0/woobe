from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from modules.artifacts.application.contracts.api import ArtifactReference, Contract, Digest, Identifier
from modules.artifacts.application.contracts.processing import ProcessingRecipe
from modules.artifacts.domain.models import Scope
from shared.security.principal import SecurityPrincipal


class ProcessingRequest(Contract):
    schema_version: Literal['1'] = '1'
    operation_id: Identifier
    revision_id: Identifier
    profile_id: Identifier | None = None
    profile_revision: int | None = Field(default=None, ge=1, le=9_223_372_036_854_775_807)

    @model_validator(mode='after')
    def validate_profile(self):
        if (self.profile_id is None) != (self.profile_revision is None):
            raise ValueError('Processing profile selection requires identity and revision')
        return self


class ProcessingJobResult(Contract):
    mode: Literal['store_only', 'extract', 'extract_index']
    processing_performed: bool
    source_sha256: Digest
    coverage: Literal['complete', 'partial', 'needs_ocr', 'unsupported'] | None = None
    representation_set_id: Identifier | None = None
    document_index_id: Identifier | None = None
    block_count: int = Field(default=0, ge=0)
    page_count: int = Field(default=0, ge=0)
    diagnostics: tuple[str, ...] = Field(default=(), max_length=32)


class ProcessingJobView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    workspace_id: Identifier
    operation_id: Identifier
    source: ArtifactReference
    profile_id: Identifier | None = None
    profile_revision: int | None = None
    recipe_fingerprint: Digest
    status: Literal['queued', 'running', 'succeeded', 'failed', 'cancel_requested', 'cancelled', 'uncertain']
    attempt: int = Field(ge=0)
    completed_stages: tuple[str, ...] = ()
    result: ProcessingJobResult | None = None
    error_code: Identifier | None = None
    retryable: bool = False


@dataclass(frozen=True)
class RequestProcessing:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    artifact_id: str
    definition: ProcessingRequest


@dataclass(frozen=True)
class ReadProcessingJob:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    job_id: str
    artifact_id: str | None = None


@dataclass(frozen=True)
class JobLease:
    id: str
    attempt_id: str
    worker_id: str
    scope: Scope
    workspace_id: str
    principal: SecurityPrincipal
    fencing_token: int
    lease_until: datetime
    lease_seconds: int
    recipe: ProcessingRecipe
    source: ArtifactReference
    profile_id: str | None
    profile_revision: int | None
    checkpoints: dict


@dataclass(frozen=True)
class WorkerPhase:
    lease: JobLease
    stage: str = ''
    checkpoint: dict | None = None
    result: dict | None = None
    status: str | None = None
    error_code: str | None = None
    retryable: bool = False


@dataclass(frozen=True)
class ClaimProcessingJob:
    worker_id: str
    lease_seconds: int = 30
    project_limit: int = 4
    workspace_limit: int = 2


class ProcessingLeaseLost(Exception):
    pass


class ProcessingCancellationRequested(Exception):
    pass
