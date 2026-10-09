"""Internal owner request for a Network's exact frozen Agent constituent.

No HTTP route accepts this request. Parent qualification remains owned by Network;
Agent rechecks its own authority and exact native content before copying.
"""
from uuid import UUID
from pydantic import Field, StrictStr
from shared.contracts.asac_requests import StrictASaCRequest


class PublishFrozenConstituent(StrictASaCRequest):
    operation_id: UUID
    parent_operation_id: UUID
    parent_resource_id: UUID
    parent_candidate_id: UUID
    parent_evaluation_id: UUID
    snapshot_id: UUID
    expected_runtime_digest: StrictStr = Field(pattern=r"^sha256:[0-9a-f]{64}$")
    reason: StrictStr = Field(min_length=3, max_length=2048)
