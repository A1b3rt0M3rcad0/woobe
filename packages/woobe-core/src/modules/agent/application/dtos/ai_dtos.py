from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from modules.agent.application.dtos.behavior_dtos import BehaviorSpecification
from modules.agent.domain.enums import (
    AgentStatus,
    AgentType,
    ContractStatus,
    CredentialStatus,
    ModelConfigStatus,
    PromptStatus,
    Provider,
    ProviderModelStatus,
    ReleaseStatus,
    ReleaseTestStatus,
    SessionMode,
    ValidationMode,
)


class CreateProviderCredentialInput(BaseModel):
    project_id: UUID
    provider: Provider
    name: str
    secret: str
    metadata: dict[str, Any] = {}


class CreateProviderCredentialOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    metadata: dict[str, Any] = {}


class UpdateProviderCredentialInput(BaseModel):
    name: str | None = None
    provider: Provider | None = None
    secret: str | None = None
    metadata: dict[str, Any] | None = None
    status: CredentialStatus | None = None


class UpdateProviderCredentialOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None
    metadata: dict[str, Any] = {}


class ListProviderCredentialsInput(BaseModel):
    project_id: UUID | None = None


class ListProviderCredentialsOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider: Provider
    name: str
    status: CredentialStatus
    created_at: datetime | None = None
    metadata: dict[str, Any] = {}


class CreateProviderModelInput(BaseModel):
    project_id: UUID
    provider_credential_id: UUID
    name: str
    model: str
    metadata: dict[str, Any] = {}


class UpdateProviderModelInput(BaseModel):
    provider_credential_id: UUID | None = None
    name: str | None = None
    model: str | None = None
    metadata: dict[str, Any] | None = None
    status: ProviderModelStatus | None = None


class ListProviderModelsInput(BaseModel):
    project_id: UUID | None = None
    provider_credential_id: UUID | None = None


class ProviderModelOutput(BaseModel):
    id: UUID
    project_id: UUID
    provider_credential_id: UUID
    provider: Provider | None = None
    name: str
    model: str
    status: ProviderModelStatus
    metadata: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CreateAgentInput(BaseModel):
    project_id: UUID
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    name: str
    description: str = ""
    type: AgentType = AgentType.chat
    behavior_spec: BehaviorSpecification | None = None
    system_prompt: str = ""
    provider: Provider = Provider.openai
    model: str
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode = SessionMode.stateless
    settings: dict[str, Any] = {}


class CreateAgentOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: AgentType
    provider: Provider
    model: str
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    status: AgentStatus
    created_at: datetime | None = None


class UpdateAgentInput(BaseModel):
    name: str | None = None
    description: str | None = None
    behavior_spec: BehaviorSpecification | None = None
    system_prompt: str | None = None
    provider: Provider | None = None
    model: str | None = None
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    fallback_credential_id: UUID | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode | None = None
    status: AgentStatus | None = None
    settings: dict[str, Any] | None = None


class UpdateAgentOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: AgentType
    provider: Provider
    model: str
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode
    behavior_spec: dict[str, Any] | None = None
    system_prompt: str
    description: str
    status: AgentStatus
    settings: dict[str, Any]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListAgentsInput(BaseModel):
    project_id: UUID | None = None


class ListAgentsOutput(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str = ""
    type: AgentType
    behavior_spec: dict[str, Any] | None = None
    system_prompt: str = ""
    provider: Provider
    model: str
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    provider_credential_id: UUID | None = None
    fallback_credential_id: UUID | None = None
    fallback_provider: Provider | None = None
    fallback_model: str | None = None
    temperature: float | None = None
    max_output_tokens: int | None = None
    session_mode: SessionMode
    status: AgentStatus
    settings: dict[str, Any] = {}
    created_at: datetime | None = None
    updated_at: datetime | None = None


class GetAgentInput(BaseModel):
    agent_id: UUID


class CreatePromptInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    name: str = ""
    content: str = ""
    content_hash: str | None = None
    created_by: UUID | None = None


class CreatePromptOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    name: str
    content: str
    status: PromptStatus
    created_by: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListPromptsOutput(BaseModel):
    id: UUID
    version: str
    name: str
    content: str
    status: PromptStatus
    content_hash: str | None = None
    created_by: UUID | None = None
    created_at: datetime | None = None


class CreateContractInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    name: str = ""
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode = ValidationMode.loose
    repair_attempts: int = 0
    additional_instructions: str | None = None
    schema_hash: str | None = None


class CreateContractOutput(BaseModel):
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
    schema_hash: str | None = None
    status: ContractStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateContractInput(BaseModel):
    name: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    validation_mode: ValidationMode | None = None
    repair_attempts: int | None = None
    additional_instructions: str | None = None
    schema_hash: str | None = None
    status: ContractStatus | None = None


class UpdateContractOutput(BaseModel):
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
    schema_hash: str | None = None
    status: ContractStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListContractsOutput(BaseModel):
    id: UUID
    version: str
    name: str
    validation_mode: ValidationMode
    status: ContractStatus
    created_at: datetime | None = None


class CreateModelConfigInput(BaseModel):
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


class CreateModelConfigOutput(BaseModel):
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


class ListModelConfigsOutput(BaseModel):
    id: UUID
    version: str
    provider: Provider
    model: str
    status: ModelConfigStatus
    created_at: datetime | None = None


class CreateReleaseInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    prompt_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    knowledge_version_id: UUID | None = None
    model_config_version_id: UUID | None = None
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    behavior_spec: BehaviorSpecification | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    external_context_contract: dict[str, Any] | None = None
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


class CreateReleaseOutput(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    status: ReleaseStatus
    snapshot_kind: str | None = None
    prompt_version_id: UUID | None = None
    contract_version_id: UUID | None = None
    knowledge_version_id: UUID | None = None
    model_config_version_id: UUID | None = None
    provider_model_id: UUID | None = None
    fallback_provider_model_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    behavior_spec: dict[str, Any] | None = None
    system_prompt: str | None = None
    response_format: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    external_context_contract: dict[str, Any] | None = None
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


class ListReleasesOutput(CreateReleaseOutput):
    pass


class PromoteReleaseInput(BaseModel):
    target_status: str = "production"
    copy_snapshot: bool = False
    release_notes: str | None = None
    user_id: UUID | None = None


class RollbackReleaseInput(BaseModel):
    user_id: UUID | None = None


class CreateReleaseTestInput(BaseModel):
    project_id: UUID
    agent_id: UUID
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    input_payload: dict[str, Any] | None = None
    expected_output: dict[str, Any] | None = None


class CreateReleaseTestOutput(BaseModel):
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


class ListReleaseTestsOutput(BaseModel):
    id: UUID
    release_id: UUID | None = None
    contract_version_id: UUID | None = None
    status: ReleaseTestStatus
    validation_errors: list[dict[str, Any]] | None = None
    latency_ms: int | None = None
    created_at: datetime | None = None
