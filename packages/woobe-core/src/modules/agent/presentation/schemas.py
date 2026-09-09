from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from modules.agent.application.dtos.behavior_dtos import BehaviorSpecification
from modules.agent.domain.enums import (
    AgentStatus,
    CollectionStatus,
    ContractStatus,
    CredentialStatus,
    DocumentStatus,
    KnowledgeVersionStatus,
    MessageRole,
    ModelConfigStatus,
    PromptStatus,
    Provider,
    ReleaseStatus,
    ReleaseTestStatus,
    RiskLevel,
    RuntimeSessionMode,
    SecretType,
    SessionMode,
    SessionStatus,
    ToolStatus,
    ToolType,
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
    behavior_spec: BehaviorSpecification | None = None
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
    behavior_spec: BehaviorSpecification | None = None
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
    behavior_spec: dict[str, Any] | None = None
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
    behavior_spec: BehaviorSpecification | None = None
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
    behavior_spec: dict[str, Any] | None = None
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
    behavior_spec: dict[str, Any] | None = None
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


class AgentCollectionResponse(BaseModel):
    id: UUID
    agent_id: UUID
    collection_id: UUID
    created_at: datetime | None = None
    updated_at: datetime | None = None


class AttachCollectionRequest(BaseModel):
    agent_id: UUID
    collection_id: UUID


class CreateCollectionRequest(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None


class CollectionResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    description: str | None
    status: CollectionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UploadDocumentRequest(BaseModel):
    project_id: UUID
    collection_id: UUID
    title: str = Field(..., min_length=1, max_length=255)
    file_name: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., max_length=128)
    size_bytes: int = Field(..., ge=0)
    storage_key: str = Field(..., max_length=512)


class DocumentResponse(BaseModel):
    id: UUID
    project_id: UUID
    collection_id: UUID
    title: str
    file_name: str
    content_type: str
    size_bytes: int
    storage_key: str
    status: DocumentStatus
    page_count: int | None = None
    chunk_count: int | None = None
    error: str | None = None
    indexed_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SearchRequest(BaseModel):
    query: str
    collection_id: UUID
    limit: int = Field(default=10, ge=1, le=100)


class ChunkResponse(BaseModel):
    id: UUID
    content: str
    chunk_index: int
    token_count: int | None = None
    page_number: int | None = None
    section_title: str | None = None
    data: dict | None = None
    score: float | None = None


class CreateKnowledgeVersionRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    version: str
    collection_ids: list[UUID] = []
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None


class KnowledgeVersionResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    version: str
    collection_ids: list[UUID]
    document_ids: list[UUID] | None = None
    snapshot_metadata: dict | None = None
    status: KnowledgeVersionStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ListKnowledgeVersionsResponse(BaseModel):
    id: UUID
    version: str
    status: KnowledgeVersionStatus
    created_at: datetime | None = None


class CreateSessionRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    mode: RuntimeSessionMode = RuntimeSessionMode.CHAT
    data: dict | None = None


class SessionResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID
    external_session_id: str | None
    tenant_id: str | None
    user_id: str | None
    status: SessionStatus
    mode: RuntimeSessionMode
    data: dict | None
    last_message_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SendMessageRequest(BaseModel):
    session_id: UUID
    content: str = Field(..., min_length=1)
    data: dict | None = None


class MessageResponse(BaseModel):
    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    data: dict | None = None
    created_at: datetime
    updated_at: datetime


class AskRequest(BaseModel):
    project_id: UUID
    agent_id: UUID
    message: str = Field(..., min_length=1)
    session_id: UUID | None = None
    tenant_id: str | None = None
    user_id: str | None = None
    metadata: dict | None = None
    execution_context: str = "playground"
    loaded_release_id: UUID | None = None
    snapshot_override: dict | None = None


class UsageResponse(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cost_usd: float | None = None


class SourceResponse(BaseModel):
    document_id: str | None = None
    document_title: str | None = None
    chunk_id: str | None = None
    page_number: int | None = None
    score: float | None = None
    content_preview: str | None = None


class ToolCallResponse(BaseModel):
    tool_name: str
    input: dict | None = None
    output: dict | None = None
    duration_ms: float | None = None
    success: bool = True
    error: str | None = None


class AskResponse(BaseModel):
    run_id: UUID | None = None
    answer: str
    session_id: UUID | None = None
    message_id: UUID | None = None
    usage: UsageResponse | None = None
    sources: list[SourceResponse] = []
    tool_calls: list[ToolCallResponse] = []
    trace_id: UUID | None = None
    model: str | None = None
    provider: str | None = None
    fallback_used: bool = False
    latency_ms: int | None = None
    parsed_output: dict | None = None
    output_parse_error: str | None = None


class CreateToolRequest(BaseModel):
    project_id: UUID
    agent_id: UUID | None = None
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    type: ToolType = ToolType.FUNCTION
    config: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel = RiskLevel.LOW
    timeout_ms: int | None = None


class ToolResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_id: UUID | None = None
    name: str
    description: str | None
    type: ToolType
    config: dict | None
    input_schema: dict | None
    output_schema: dict | None
    risk_level: RiskLevel
    timeout_ms: int | None
    status: ToolStatus
    created_at: datetime | None = None
    updated_at: datetime | None = None


class UpdateToolRequest(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = None
    agent_id: UUID | None = None
    config: dict | None = None
    input_schema: dict | None = None
    output_schema: dict | None = None
    risk_level: RiskLevel | None = None
    timeout_ms: int | None = None


class UpdateToolStatusRequest(BaseModel):
    status: ToolStatus


class TestToolRequest(BaseModel):
    config: dict
    input_data: dict | None = None


class TestToolResponse(BaseModel):
    success: bool
    status_code: int | None = None
    headers: dict | None = None
    body: str | None = None
    duration_ms: float | None = None
    error: str | None = None


class ExecuteToolRequest(BaseModel):
    tool_id: UUID
    input_data: dict | None = None
    agent_id: UUID | None = None


class ExecuteToolResponse(BaseModel):
    success: bool
    output: dict | None = None
    duration_ms: float | None = None
    error: str | None = None


class CreateSecretRequest(BaseModel):
    project_id: UUID
    name: str = Field(..., min_length=1, max_length=255)
    type: SecretType = SecretType.CUSTOM
    value: str = Field(..., min_length=1)


class SecretResponse(BaseModel):
    id: UUID
    project_id: UUID
    name: str
    type: SecretType
    data: dict | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
