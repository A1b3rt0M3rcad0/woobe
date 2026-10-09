"""Non-circular Git evidence issued by an explicitly trusted pipeline."""
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictInt, StrictStr
from shared.contracts.asac_requests import StrictASaCRequest, DIGEST, REVISION
from shared.contracts.asac_publication import GitPublicationClaim


class GitAttestationPayload(GitPublicationClaim):
    format: Literal['woobe-git-attestation']
    schema_version: Literal['1.0']
    issuer: StrictStr = Field(min_length=1,max_length=128)
    instance_id: UUID
    project_id: UUID
    resource_id: UUID
    kind: Literal['Agent','Network']
    publication_id: UUID
    revision_id: StrictStr = Field(pattern=REVISION)
    record_digest: StrictStr = Field(pattern=DIGEST)
    definition_digest: StrictStr = Field(pattern=DIGEST)
    author_artifact_digest: StrictStr = Field(pattern=DIGEST)
    workflow_run: StrictStr = Field(min_length=1,max_length=256)
    issued_at: StrictInt = Field(ge=1)
    expires_at: StrictInt = Field(ge=1)


class SignedGitAttestation(StrictASaCRequest):
    payload: GitAttestationPayload
    payload_digest: StrictStr = Field(pattern=DIGEST)
    signature: StrictStr = Field(pattern=r'^[A-Za-z0-9_-]{86}$')


class AcceptGitAttestation(StrictASaCRequest):
    operation_id: UUID
    attestation: SignedGitAttestation
