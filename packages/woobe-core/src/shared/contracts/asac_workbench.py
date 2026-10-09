"""Owner-authorized Web editor requests; content is validated by Package."""
from pydantic import Field, StrictInt, StrictStr, model_validator
from uuid import UUID
from shared.contracts.asac_requests import StrictASaCRequest, ASaCLeaseProof, REVISION


class ASaCFileEdit(StrictASaCRequest):
    path: StrictStr = Field(min_length=1,max_length=512)
    content: StrictStr = Field(max_length=1048576)


class EditASaCDraft(StrictASaCRequest):
    operation_id: UUID
    expected_generation: StrictInt = Field(ge=1)
    leases: list[ASaCLeaseProof] | None = Field(default=None,max_length=2)
    files: list[ASaCFileEdit] = Field(min_length=1,max_length=64)

    @model_validator(mode='after')
    def bounded_content(self):
        if sum(len(item.content.encode('utf-8')) for item in self.files)>4*1048576:
            raise ValueError('Editor content exceeds byte limit')
        if len({item.path for item in self.files})!=len(self.files):
            raise ValueError('Editor paths must be distinct')
        return self


class CheckpointASaCDraft(StrictASaCRequest):
    operation_id: UUID
    expected_generation: StrictInt = Field(ge=1)
    leases: list[ASaCLeaseProof] | None = Field(default=None,max_length=2)
    revision_id: StrictStr = Field(pattern=REVISION)
    message: StrictStr = Field(min_length=1,max_length=4096)
    parents: list[StrictStr] = Field(default_factory=list,max_length=64)


class StageWorkbenchDraft(StrictASaCRequest):
    operation_id: UUID
    expected_generation: StrictInt = Field(ge=1)
    revision_id: StrictStr = Field(pattern=REVISION)
