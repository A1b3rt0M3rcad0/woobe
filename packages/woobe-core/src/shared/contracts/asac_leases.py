"""Workflow identity never comes from credential reuse or a client clock."""
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictInt, StrictStr, model_validator
from shared.contracts.asac_requests import StrictASaCRequest, ASaCLeaseProof


class ASaCLeaseScope(StrictASaCRequest):
    scope: Literal['resource', 'draft', 'staging', 'production']
    draft_id: UUID | None = None

    @model_validator(mode='after')
    def draft_scope_only(self):
        if self.draft_id is not None and self.scope != 'draft':
            raise ValueError('Draft identity applies only to a Draft lease')
        return self

    def key(self):
        return f'draft:{self.draft_id or "native"}' if self.scope == 'draft' else self.scope


class AcquireASaCLease(ASaCLeaseScope):
    operation_id: UUID
    workflow_id: UUID
    ttl_seconds: StrictInt = Field(ge=1, le=86400)


class ChangeASaCLease(ASaCLeaseScope, ASaCLeaseProof):
    operation_id: UUID


class RenewASaCLease(ChangeASaCLease):
    ttl_seconds: StrictInt = Field(ge=1, le=86400)


class BreakASaCLease(ASaCLeaseScope):
    operation_id: UUID
    lease_id: UUID
    fencing_token: StrictInt = Field(ge=1)
    reason: StrictStr = Field(min_length=3, max_length=2048)

    @model_validator(mode='after')
    def audit_reason(self):
        if len(self.reason.strip()) < 3:
            raise ValueError('Administrative break requires a meaningful audit reason')
        return self
