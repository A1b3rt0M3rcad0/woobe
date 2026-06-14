from modules.agent.domain.entities import (
    Agent,
    AgentCollection,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    Document,
    DocumentChunk,
    DocumentCollection,
    KnowledgeVersion,
    ProviderCredential,
)
from modules.agent.domain.enums import (
    AgentStatus,
    AgentType,
    CollectionStatus,
    ContractStatus,
    CredentialStatus,
    DocumentStatus,
    KnowledgeVersionStatus,
    ModelConfigStatus,
    ParserType,
    PromptStatus,
    Provider,
    ReleaseStatus,
    ReleaseTestStatus,
    SessionMode,
    ValidationMode,
)
from modules.agent.infra.database.models import (
    AgentCollectionModel,
    AgentContractModel,
    AgentModel,
    AgentModelConfigModel,
    AgentPromptModel,
    AgentReleaseModel,
    AgentReleaseTestModel,
    DocumentChunkModel,
    DocumentCollectionModel,
    DocumentModel,
    KnowledgeVersionModel,
    ProviderCredentialModel,
)


def provider_credential_model_to_entity(
    model: ProviderCredentialModel,
) -> ProviderCredential:
    return ProviderCredential(
        id=model.id,
        project_id=model.project_id,
        provider=Provider(model.provider),
        name=model.name,
        encrypted_secret=model.encrypted_secret,
        status=CredentialStatus(model.status),
        last_validated_at=model.last_validated_at,
        metadata=model.meta or {},
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def provider_credential_entity_to_model(
    entity: ProviderCredential,
) -> ProviderCredentialModel:
    return ProviderCredentialModel(
        id=entity.id,
        project_id=entity.project_id,
        provider=entity.provider.value,
        name=entity.name,
        encrypted_secret=entity.encrypted_secret,
        status=entity.status.value,
        last_validated_at=entity.last_validated_at,
        meta=entity.metadata or None,
    )


def agent_model_to_entity(model: AgentModel) -> Agent:
    return Agent(
        id=model.id,
        project_id=model.project_id,
        provider_credential_id=model.provider_credential_id,
        fallback_credential_id=model.fallback_credential_id,
        name=model.name,
        description=model.description,
        type=AgentType(model.type),
        system_prompt=model.system_prompt,
        provider=Provider(model.provider),
        model=model.model,
        fallback_provider=Provider(model.fallback_provider) if model.fallback_provider else None,
        fallback_model=model.fallback_model,
        temperature=model.temperature,
        max_output_tokens=model.max_output_tokens,
        session_mode=SessionMode(model.session_mode),
        status=AgentStatus(model.status),
        settings=model.settings,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_entity_to_model(entity: Agent) -> AgentModel:
    return AgentModel(
        id=entity.id,
        project_id=entity.project_id,
        provider_credential_id=entity.provider_credential_id,
        fallback_credential_id=entity.fallback_credential_id,
        name=entity.name,
        description=entity.description,
        type=entity.type.value,
        system_prompt=entity.system_prompt,
        provider=entity.provider.value,
        model=entity.model,
        fallback_provider=entity.fallback_provider.value if entity.fallback_provider else None,
        fallback_model=entity.fallback_model,
        temperature=entity.temperature,
        max_output_tokens=entity.max_output_tokens,
        session_mode=entity.session_mode.value,
        status=entity.status.value,
        settings=entity.settings,
    )


def agent_prompt_model_to_entity(model: AgentPromptModel) -> AgentPrompt:
    return AgentPrompt(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        version=model.version,
        name=model.name,
        content=model.content,
        content_hash=model.content_hash,
        status=PromptStatus(model.status),
        created_by=model.created_by,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_prompt_entity_to_model(entity: AgentPrompt) -> AgentPromptModel:
    return AgentPromptModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        version=entity.version,
        name=entity.name,
        content=entity.content,
        content_hash=entity.content_hash,
        status=entity.status.value,
        created_by=entity.created_by,
    )


def agent_contract_model_to_entity(model: AgentContractModel) -> AgentContract:
    return AgentContract(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        version=model.version,
        name=model.name,
        input_schema=model.input_schema,
        output_schema=model.output_schema,
        validation_mode=ValidationMode(model.validation_mode),
        repair_attempts=model.repair_attempts,
        additional_instructions=model.additional_instructions,
        schema_hash=model.schema_hash,
        status=ContractStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_contract_entity_to_model(entity: AgentContract) -> AgentContractModel:
    return AgentContractModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        version=entity.version,
        name=entity.name,
        input_schema=entity.input_schema,
        output_schema=entity.output_schema,
        validation_mode=entity.validation_mode.value,
        repair_attempts=entity.repair_attempts,
        additional_instructions=entity.additional_instructions,
        schema_hash=entity.schema_hash,
        status=entity.status.value,
    )


def agent_model_config_model_to_entity(model: AgentModelConfigModel) -> AgentModelConfig:
    return AgentModelConfig(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        version=model.version,
        provider=Provider(model.provider),
        provider_credential_id=model.provider_credential_id,
        model=model.model,
        base_url=model.base_url,
        temperature=model.temperature,
        max_output_tokens=model.max_output_tokens,
        session_mode=SessionMode(model.session_mode) if model.session_mode else None,
        settings=model.settings,
        status=ModelConfigStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_model_config_entity_to_model(entity: AgentModelConfig) -> AgentModelConfigModel:
    return AgentModelConfigModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        version=entity.version,
        provider=entity.provider.value,
        provider_credential_id=entity.provider_credential_id,
        model=entity.model,
        base_url=entity.base_url,
        temperature=entity.temperature,
        max_output_tokens=entity.max_output_tokens,
        session_mode=entity.session_mode.value if entity.session_mode else None,
        settings=entity.settings,
        status=entity.status.value,
    )


def agent_release_model_to_entity(model: AgentReleaseModel) -> AgentRelease:
    return AgentRelease(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        version=model.version,
        status=ReleaseStatus(model.status),
        prompt_version_id=model.prompt_version_id,
        contract_version_id=model.contract_version_id,
        knowledge_version_id=model.knowledge_version_id,
        model_config_version_id=model.model_config_version_id,
        name=model.name,
        description=model.description,
        system_prompt=model.system_prompt,
        response_format=model.response_format,
        output_schema=model.output_schema,
        provider=model.provider,
        model=model.model,
        provider_credential_id=model.provider_credential_id,
        fallback_provider=model.fallback_provider,
        fallback_model=model.fallback_model,
        fallback_credential_id=model.fallback_credential_id,
        base_url=model.base_url,
        temperature=model.temperature,
        max_output_tokens=model.max_output_tokens,
        session_mode=model.session_mode,
        agent_status=model.agent_status,
        collection_ids=list(model.collection_ids) if model.collection_ids else None,
        runtime_config=model.runtime_config,
        release_notes=model.release_notes,
        risk_score=model.risk_score,
        created_by=model.created_by,
        promoted_by=model.promoted_by,
        promoted_at=model.promoted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_release_entity_to_model(entity: AgentRelease) -> AgentReleaseModel:
    return AgentReleaseModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        version=entity.version,
        status=entity.status.value,
        prompt_version_id=entity.prompt_version_id,
        contract_version_id=entity.contract_version_id,
        knowledge_version_id=entity.knowledge_version_id,
        model_config_version_id=entity.model_config_version_id,
        name=entity.name,
        description=entity.description,
        system_prompt=entity.system_prompt,
        response_format=entity.response_format,
        output_schema=entity.output_schema,
        provider=entity.provider,
        model=entity.model,
        provider_credential_id=entity.provider_credential_id,
        fallback_provider=entity.fallback_provider,
        fallback_model=entity.fallback_model,
        fallback_credential_id=entity.fallback_credential_id,
        base_url=entity.base_url,
        temperature=entity.temperature,
        max_output_tokens=entity.max_output_tokens,
        session_mode=entity.session_mode,
        agent_status=entity.agent_status,
        collection_ids=entity.collection_ids,
        runtime_config=entity.runtime_config,
        release_notes=entity.release_notes,
        risk_score=entity.risk_score,
        created_by=entity.created_by,
        promoted_by=entity.promoted_by,
        promoted_at=entity.promoted_at,
    )


def agent_release_test_model_to_entity(model: AgentReleaseTestModel) -> AgentReleaseTest:
    return AgentReleaseTest(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        release_id=model.release_id,
        contract_version_id=model.contract_version_id,
        input_payload=model.input_payload,
        expected_output=model.expected_output,
        actual_output=model.actual_output,
        status=ReleaseTestStatus(model.status),
        validation_errors=model.validation_errors,
        latency_ms=model.latency_ms,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def agent_release_test_entity_to_model(entity: AgentReleaseTest) -> AgentReleaseTestModel:
    return AgentReleaseTestModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        release_id=entity.release_id,
        contract_version_id=entity.contract_version_id,
        input_payload=entity.input_payload,
        expected_output=entity.expected_output,
        actual_output=entity.actual_output,
        status=entity.status.value,
        validation_errors=entity.validation_errors,
        latency_ms=entity.latency_ms,
    )


def agent_collection_to_model(entity: AgentCollection) -> AgentCollectionModel:
    return AgentCollectionModel(
        id=entity.id,
        agent_id=entity.agent_id,
        collection_id=entity.collection_id,
    )


def agent_collection_model_to_entity(model: AgentCollectionModel) -> AgentCollection:
    return AgentCollection(
        id=model.id,
        agent_id=model.agent_id,
        collection_id=model.collection_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def collection_to_model(entity: DocumentCollection) -> DocumentCollectionModel:
    return DocumentCollectionModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        description=entity.description,
        status=entity.status.value if isinstance(entity.status, CollectionStatus) else entity.status,
    )


def model_to_collection(model: DocumentCollectionModel) -> DocumentCollection:
    return DocumentCollection(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        description=model.description,
        status=CollectionStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def document_to_model(entity: Document) -> DocumentModel:
    return DocumentModel(
        id=entity.id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        title=entity.title,
        file_name=entity.file_name,
        content_type=entity.content_type,
        size_bytes=entity.size_bytes,
        storage_key=entity.storage_key,
        parser=entity.parser.value if isinstance(entity.parser, ParserType) else entity.parser,
        status=entity.status.value if isinstance(entity.status, DocumentStatus) else entity.status,
        error=entity.error,
        page_count=entity.page_count,
        chunk_count=entity.chunk_count,
        sha256=entity.sha256,
        indexed_at=entity.indexed_at,
    )


def model_to_document(model: DocumentModel) -> Document:
    return Document(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        title=model.title,
        file_name=model.file_name,
        content_type=model.content_type,
        size_bytes=model.size_bytes,
        storage_key=model.storage_key,
        parser=ParserType(model.parser),
        status=DocumentStatus(model.status),
        error=model.error,
        page_count=model.page_count,
        chunk_count=model.chunk_count,
        sha256=model.sha256,
        indexed_at=model.indexed_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def chunk_to_model(entity: DocumentChunk) -> DocumentChunkModel:
    return DocumentChunkModel(
        id=entity.id,
        project_id=entity.project_id,
        collection_id=entity.collection_id,
        document_id=entity.document_id,
        content=entity.content,
        chunk_index=entity.chunk_index,
        token_count=entity.token_count,
        page_number=entity.page_number,
        section_title=entity.section_title,
        data=entity.data,
        embedding=entity.embedding,
    )


def model_to_chunk(model: DocumentChunkModel) -> DocumentChunk:
    return DocumentChunk(
        id=model.id,
        project_id=model.project_id,
        collection_id=model.collection_id,
        document_id=model.document_id,
        content=model.content,
        chunk_index=model.chunk_index,
        token_count=model.token_count,
        page_number=model.page_number,
        section_title=model.section_title,
        data=model.data,
        embedding=model.embedding,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def knowledge_version_to_model(entity: KnowledgeVersion) -> KnowledgeVersionModel:
    return KnowledgeVersionModel(
        id=entity.id,
        project_id=entity.project_id,
        agent_id=entity.agent_id,
        version=entity.version,
        collection_ids=entity.collection_ids or [],
        document_ids=entity.document_ids,
        snapshot_metadata=entity.snapshot_metadata,
        status=entity.status.value if isinstance(entity.status, KnowledgeVersionStatus) else entity.status,
    )


def knowledge_version_model_to_entity(model: KnowledgeVersionModel) -> KnowledgeVersion:
    return KnowledgeVersion(
        id=model.id,
        project_id=model.project_id,
        agent_id=model.agent_id,
        version=model.version,
        collection_ids=list(model.collection_ids or []),
        document_ids=list(model.document_ids) if model.document_ids else None,
        snapshot_metadata=model.snapshot_metadata,
        status=KnowledgeVersionStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )
