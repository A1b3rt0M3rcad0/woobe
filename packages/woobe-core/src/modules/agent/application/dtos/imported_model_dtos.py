from uuid import UUID

from pydantic import Field

from modules.agent.application.dtos.ai_dtos import CreateProviderModelInput


class ResolveImportedModelInput(CreateProviderModelInput):
    expected_spec_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    expected_credential_revision: str | None = None
    expected_model_id: UUID | None = None
    expected_model_revision: str | None = None
