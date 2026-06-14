from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from modules.agent.domain.enums import (
    AgentStatus,
    ContractStatus,
    CredentialStatus,
    ModelConfigStatus,
    PromptStatus,
    Provider,
    ReleaseStatus,
    ReleaseTestStatus,
    SessionMode,
    ValidationMode,
)


class CreateProviderCredentialRequest(BaseModel):
    project_id: UUID
    provider: Provider
    name: str
    secret: str
    metadata: dict[str, Any] = {}


class ProviderCredentialResponse(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    metadata: dict[str, Any] = {}


class UpdateProviderCredentialRequest(BaseModel):
    name: str | None = None
    provider: Provider | None = None
    secret: str | None = None
    metadata: dict[str, Any] | None = None
    status: CredentialStatus | None = None


class CreateAgentRequest(BaseModel):
    project_id: UUID
    name: str
    provider: Provider = Provider.openai
    model: str
    system_prompt: str = ""
    description: str = ""
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateful
    settings: dict[str, Any] = {}


class UpdateAgentRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    provider: Provider | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    status: AgentStatus | None = None
    settings: dict[str, Any] | None = None


class AgentResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    provider: Provider
    model: str
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    system_prompt: str = ""
    description: str = ""
    status: AgentStatus
    settings: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreatePromptRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    name: str = ""
    content: str = ""
    content_hash: str | None = None


class PromptResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    name: str
    content: str
    status: PromptStatus
    content_hash: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListPromptsResponse(BaseModel):
    id: UUID
    version: str
    name: str
    status: PromptStatus
    created_at: datetime | None = None


class CreateContractRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    name: str = ""
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode = ValidationMode.loose
    repair_attempts: int = 0
    additional_instructions: str | None = None


class UpdateContractRequest(BaseModel):
    name: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode | None = None
    repair_attempts: int | None = None
    additional_instructions: str | None = None
    status: ContractStatus | None = None


class ContractResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    name: str
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode
    repair_attempts: int
    additional_instructions: str | None = None
    status: ContractStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListContractsResponse(BaseModel):
    id: UUID
    version: str
    name: str
    validation_mode: ValidationMode
    status: ContractStatus
    created_at: datetime | None = None


class CreateModelConfigRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    provider: Provider = Provider.openai
    provider_credential_id: UUID | None = None
    model: str
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    settings: dict[str, Any] = {}


class ModelConfigResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    provider: Provider
    provider_credential_id: UUID | None = None
    model: str
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    settings: dict[str, Any]
    status: ModelConfigStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListModelConfigsResponse(BaseModel):
    id: UUID
    version: str
    provider: Provider
    model: str
    status: ModelConfigStatus
    created_at: datetime | None = None


class CreateReleaseRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    prompt_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    knowledge_version_id: UUID | None = None
    model_config_version_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: str | None = None
    agent_status: str | None = None
    collection_ids: list[UUID] | None = None
    runtime_config: dict[str, Any] | None = None
    release_notes: str | None = None
    risk_score: int | None = None


class ReleaseResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    status: ReleaseStatus
    prompt_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    knowledge_version_id: UUID | None = None
    model_config_version_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    provider: str | None = None
    model: str | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: str | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    base_url: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: str | None = None
    agent_status: str | None = None
    collection_ids: list[UUID] | None = None
    runtime_config: dict[str, Any] | None = None
    release_notes: str | None = None
    risk_score: int | None = None
    created_by: UUID | None = None
    promoted_by: UUID | None = None
    promoted_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListReleasesResponse(BaseModel):
    id: UUID
    version: str
    status: ReleaseStatus
    name: str | None = None
    provider: str | None = None
    model: str | None = None
    system_prompt: str | None = None
    output_schema: dict[str, Any] | None = None
    risk_score: int | None = None
    release_notes: str | None = None
    created_at: datetime | None = None
    promoted_at: datetime | None = None


class PromoteReleaseRequest(BaseModel):
    user_id: UUID | None = None


class RollbackReleaseRequest(BaseModel):
    user_id: UUID | None = None


class CreateReleaseTestRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    input_payload: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None


class ReleaseTestResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    input_payload: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None
    actual_output: dict[str, Any] | None = None
    status: ReleaseTestStatus
    validation_errors: list[dict[str, Any]] | None = None
    latency_ms: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListReleaseTestsResponse(BaseModel):
    id: UUID
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    status: ReleaseTestStatus
    latency_ms: int | None = None
    created_at: datetime | None = None
