"""Bounded model operations over untrusted, locally verified document fragments."""
from dataclasses import dataclass
import math
from typing import Literal

from pydantic import Field

from modules.artifacts.application.contracts.api import Contract, Digest, Identifier, SourceReference
from modules.artifacts.application.contracts.jobs import JobLease
from modules.artifacts.application.contracts.processing import ProcessingModelReference
from modules.artifacts.domain.models import Scope, sha256_digest
from shared.security.principal import SecurityPrincipal


MAX_MODEL_CALLS = 4
MAX_MODEL_INPUT_BYTES = 32_768
MAX_JOB_MODEL_TOKENS = 100_000
MAX_MODEL_TIMEOUT_SECONDS = 60


class DocumentModelFragment(Contract):
    id: Identifier
    text: str = Field(min_length=1, max_length=8192)
    source: SourceReference
    trust: Literal['untrusted_document'] = 'untrusted_document'


class DocumentSummaryProposal(Contract):
    text: str = Field(min_length=1, max_length=8192)
    fragment_ids: tuple[Identifier, ...] = Field(min_length=1, max_length=16)


class DocumentSectionProposal(Contract):
    title: str = Field(min_length=1, max_length=512)
    start_fragment_id: Identifier
    end_fragment_id: Identifier


class DocumentModelOutput(Contract):
    schema_version: Literal['1'] = '1'
    summaries: tuple[DocumentSummaryProposal, ...] = Field(default=(), max_length=16)
    sections: tuple[DocumentSectionProposal, ...] = Field(default=(), max_length=64)


@dataclass(frozen=True)
class DocumentModelBindingRequest:
    principal: SecurityPrincipal
    scope: Scope
    workspace_id: str
    reference: ProcessingModelReference


@dataclass(frozen=True)
class DocumentModelCall:
    lease: JobLease
    call_id: str
    operation: Literal['summarize', 'refine_structure']
    fragments: tuple[DocumentModelFragment, ...]
    max_output_tokens: int
    timeout_seconds: int


@dataclass(frozen=True)
class DocumentModelUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    cost_status: str = 'unknown'
    provider_request_id: str | None = None

    def __post_init__(self):
        for value in (self.input_tokens, self.output_tokens):
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError('Reported model tokens must be non-negative integers or unknown')
        if self.cost_usd is not None and (not math.isfinite(self.cost_usd) or self.cost_usd < 0):
            raise ValueError('Reported model cost must be finite and non-negative or unknown')
        if self.cost_status not in {'reported', 'estimated', 'unknown'}:
            raise ValueError('Invalid model cost provenance')


@dataclass(frozen=True)
class DocumentModelResponse:
    output: DocumentModelOutput
    usage: DocumentModelUsage
    binding_fingerprint: str

    def __post_init__(self):
        sha256_digest(self.binding_fingerprint)


class DocumentModelCallView(Contract):
    schema_version: Literal['1'] = '1'
    id: Identifier
    job_id: Identifier
    operation: Literal['summarize', 'refine_structure']
    input_fingerprint: Digest
    binding_fingerprint: Digest
    state: Literal['admitted', 'in_flight', 'completed', 'failed', 'uncertain']
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost_usd: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    cost_status: Literal['reported', 'estimated', 'unknown'] = 'unknown'
    error_code: str | None = None


@dataclass(frozen=True)
class DocumentModelPhase:
    call: DocumentModelCall
    receipt: dict | None = None
    usage: DocumentModelUsage | None = None
    output: DocumentModelOutput | None = None
    error_code: str | None = None
    uncertain: bool = False
