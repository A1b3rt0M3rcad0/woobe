"""A frozen deployment plan is distinct from publication and authoring."""
from typing import Literal
from uuid import UUID
from pydantic import Field, StrictInt, StrictStr, model_validator
from shared.contracts.asac_requests import StrictASaCRequest, ASaCLeaseProof


class PlanASaCDeployment(StrictASaCRequest):
    operation_id: UUID
    release_id: UUID
    publication_id: UUID | None = None
    environment: Literal['staging','production'] = 'production'
    expected_generation: StrictInt = Field(ge=0)
    action: Literal['activate','rollback'] = 'activate'
    reason: StrictStr = Field(min_length=3,max_length=2048)

    @model_validator(mode='after')
    def meaningful_reason(self):
        if len(self.reason.strip()) < 3:
            raise ValueError('A deployment requires a meaningful audit reason')
        return self


class ApplyASaCDeployment(StrictASaCRequest):
    operation_id: UUID
    plan_id: UUID
    environment: Literal['staging','production']
    leases: list[ASaCLeaseProof] = Field(min_length=1,max_length=1)
