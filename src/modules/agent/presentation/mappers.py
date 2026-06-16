from typing import Any

from modules.agent.domain.entities import (
    Agent,
    AgentContract,
    AgentModelConfig,
    AgentPrompt,
    AgentRelease,
    AgentReleaseTest,
    Document,
    DocumentCollection,
    ProviderCredential,
)
from modules.agent.presentation.schemas import (
    AgentCollectionResponse,
    AgentResponse,
    ChunkResponse,
    CollectionResponse,
    ContractResponse,
    DocumentResponse,
    KnowledgeVersionResponse,
    ListContractsResponse,
    ListKnowledgeVersionsResponse,
    ListModelConfigsResponse,
    ListPromptsResponse,
    ListReleaseTestsResponse,
    ListReleasesResponse,
    ModelConfigResponse,
    PromptResponse,
    ProviderCredentialResponse,
    ReleaseResponse,
    ReleaseTestResponse,
)
from modules.agent.application.dtos import (
    AgentCollectionOutput,
    AttachCollectionOutput,
    CreateCollectionOutput,
    DocumentChunkOutput,
    UploadDocumentOutput,
)


def credential_to_response(credential: ProviderCredential) -> ProviderCredentialResponse:
    return ProviderCredentialResponse(
        id=credential.id,
        project_id=credential.project_id,
        provider=credential.provider.value if hasattr(credential.provider, 'value') else credential.provider,
        name=credential.name,
        status=credential.status.value if hasattr(credential.status, 'value') else credential.status,
        created_at=credential.created_at,
        metadata=credential.metadata,
    )


def agent_to_response(agent: Agent) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        provider=agent.provider.value if hasattr(agent.provider, 'value') else agent.provider,
        model=agent.model,
        provider_credential_id=agent.provider_credential_id,
        fallback_credential_id=agent.fallback_credential_id,
        fallback_provider=agent.fallback_provider.value if (hasattr(agent.fallback_provider, 'value') and agent.fallback_provider) else agent.fallback_provider,
        fallback_model=agent.fallback_model,
        temperature=agent.temperature,
        max_output_tokens=agent.max_output_tokens,
        session_mode=agent.session_mode.value if hasattr(agent.session_mode, 'value') else agent.session_mode,
        system_prompt=agent.system_prompt,
        description=agent.description,
        status=agent.status.value if hasattr(agent.status, 'value') else agent.status,
        settings=agent.settings,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def prompt_to_response(prompt: AgentPrompt) -> PromptResponse:
    return PromptResponse(
        id=prompt.id,
        project_id=prompt.project_id,
        agent_id=prompt.agent_id,
        version=prompt.version,
        name=prompt.name,
        content=prompt.content,
        status=prompt.status.value if hasattr(prompt.status, 'value') else prompt.status,
        content_hash=prompt.content_hash,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


def list_prompts_to_response(prompt: AgentPrompt) -> ListPromptsResponse:
    return ListPromptsResponse(
        id=prompt.id,
        version=prompt.version,
        name=prompt.name,
        status=prompt.status.value if hasattr(prompt.status, 'value') else prompt.status,
        created_at=prompt.created_at,
    )


def contract_to_response(contract: AgentContract) -> ContractResponse:
    return ContractResponse(
        id=contract.id,
        project_id=contract.project_id,
        agent_id=contract.agent_id,
        version=contract.version,
        name=contract.name,
        input_schema=contract.input_schema,
        output_schema=contract.output_schema,
        validation_mode=contract.validation_mode.value if hasattr(contract.validation_mode, 'value') else contract.validation_mode,
        repair_attempts=contract.repair_attempts,
        additional_instructions=contract.additional_instructions,
        status=contract.status.value if hasattr(contract.status, 'value') else contract.status,
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


def list_contracts_to_response(contract: AgentContract) -> ListContractsResponse:
    return ListContractsResponse(
        id=contract.id,
        version=contract.version,
        name=contract.name,
        validation_mode=contract.validation_mode.value if hasattr(contract.validation_mode, 'value') else contract.validation_mode,
        status=contract.status.value if hasattr(contract.status, 'value') else contract.status,
        created_at=contract.created_at,
    )


def model_config_to_response(config: AgentModelConfig) -> ModelConfigResponse:
    return ModelConfigResponse(
        id=config.id,
        project_id=config.project_id,
        agent_id=config.agent_id,
        version=config.version,
        provider=config.provider.value if hasattr(config.provider, 'value') else config.provider,
        provider_credential_id=config.provider_credential_id,
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        session_mode=config.session_mode.value if (hasattr(config.session_mode, 'value') and config.session_mode) else config.session_mode,
        settings=config.settings,
        status=config.status.value if hasattr(config.status, 'value') else config.status,
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def list_model_configs_to_response(config: AgentModelConfig) -> ListModelConfigsResponse:
    return ListModelConfigsResponse(
        id=config.id,
        version=config.version,
        provider=config.provider.value if hasattr(config.provider, 'value') else config.provider,
        model=config.model,
        status=config.status.value if hasattr(config.status, 'value') else config.status,
        created_at=config.created_at,
    )


def release_to_response(release: AgentRelease) -> ReleaseResponse:
    return ReleaseResponse(
        id=release.id,
        project_id=release.project_id,
        agent_id=release.agent_id,
        version=release.version,
        status=release.status.value if hasattr(release.status, 'value') else release.status,
        prompt_version_id=release.prompt_version_id,
        contract_version_id=release.contract_version_id,
        knowledge_version_id=release.knowledge_version_id,
        model_config_version_id=release.model_config_version_id,
        name=release.name,
        description=release.description,
        system_prompt=release.system_prompt,
        response_format=release.response_format,
        output_schema=release.output_schema,
        provider=release.provider,
        model=release.model,
        provider_credential_id=release.provider_credential_id,
        fallback_provider=release.fallback_provider,
        fallback_model=release.fallback_model,
        fallback_credential_id=release.fallback_credential_id,
        base_url=release.base_url,
        temperature=release.temperature,
        max_output_tokens=release.max_output_tokens,
        session_mode=release.session_mode,
        agent_status=release.agent_status,
        collection_ids=release.collection_ids,
        runtime_config=release.runtime_config,
        release_notes=release.release_notes,
        risk_score=release.risk_score,
        created_by=release.created_by,
        promoted_by=release.promoted_by,
        promoted_at=release.promoted_at,
        created_at=release.created_at,
        updated_at=release.updated_at,
    )


def list_releases_to_response(release: AgentRelease | Any) -> ListReleasesResponse:
    return ListReleasesResponse(
        id=release.id,
        version=release.version,
        status=release.status.value if hasattr(release.status, 'value') else release.status,
        name=release.name if hasattr(release, 'name') else None,
        provider=release.provider if hasattr(release, 'provider') else None,
        model=release.model if hasattr(release, 'model') else None,
        system_prompt=release.system_prompt if hasattr(release, 'system_prompt') else None,
        output_schema=release.output_schema if hasattr(release, 'output_schema') else None,
        risk_score=release.risk_score,
        release_notes=release.release_notes,
        created_at=release.created_at,
        promoted_at=release.promoted_at,
    )


def release_test_to_response(test: AgentReleaseTest) -> ReleaseTestResponse:
    return ReleaseTestResponse(
        id=test.id,
        project_id=test.project_id,
        agent_id=test.agent_id,
        release_id=test.release_id,
        contract_version_id=test.contract_version_id,
        input_payload=test.input_payload,
        expected_output=test.expected_output,
        actual_output=test.actual_output,
        status=test.status.value if hasattr(test.status, 'value') else test.status,
        validation_errors=test.validation_errors,
        latency_ms=test.latency_ms,
        created_at=test.created_at,
        updated_at=test.updated_at,
    )


def list_release_tests_to_response(test: AgentReleaseTest) -> ListReleaseTestsResponse:
    return ListReleaseTestsResponse(
        id=test.id,
        release_id=test.release_id,
        contract_version_id=test.contract_version_id,
        status=test.status.value if hasattr(test.status, 'value') else test.status,
        latency_ms=test.latency_ms,
        created_at=test.created_at,
    )


def collection_to_response(collection: DocumentCollection) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        project_id=collection.project_id,
        name=collection.name,
        description=collection.description,
        status=collection.status,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def create_collection_output_to_response(output: CreateCollectionOutput) -> CollectionResponse:
    return CollectionResponse(
        id=output.id,
        project_id=output.project_id,
        name=output.name,
        description=output.description,
        status=output.status,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def agent_collection_output_to_response(output: AgentCollectionOutput) -> AgentCollectionResponse:
    return AgentCollectionResponse(
        id=output.id,
        agent_id=output.agent_id,
        collection_id=output.collection_id,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def attach_collection_output_to_response(output: AttachCollectionOutput) -> AgentCollectionResponse:
    return AgentCollectionResponse(
        id=output.id,
        agent_id=output.agent_id,
        collection_id=output.collection_id,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def document_to_response(document: Document) -> DocumentResponse:
    return DocumentResponse(
        id=document.id,
        project_id=document.project_id,
        collection_id=document.collection_id,
        title=document.title,
        file_name=document.file_name,
        content_type=document.content_type,
        size_bytes=document.size_bytes,
        storage_key=document.storage_key,
        status=document.status,
        page_count=document.page_count,
        chunk_count=document.chunk_count,
        error=document.error,
        indexed_at=document.indexed_at,
        created_at=document.created_at,
        updated_at=document.updated_at,
    )


def upload_document_output_to_response(output: UploadDocumentOutput) -> DocumentResponse:
    return DocumentResponse(
        id=output.id,
        project_id=output.project_id,
        collection_id=output.collection_id,
        title=output.title,
        file_name=output.file_name,
        content_type=output.content_type,
        size_bytes=output.size_bytes,
        storage_key=output.storage_key,
        status=output.status,
        page_count=output.page_count,
        chunk_count=output.chunk_count,
        error=output.error,
        indexed_at=output.indexed_at,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def knowledge_version_to_response(version) -> KnowledgeVersionResponse:
    return KnowledgeVersionResponse(
        id=version.id, project_id=version.project_id, agent_id=version.agent_id,
        version=version.version, collection_ids=version.collection_ids or [],
        document_ids=version.document_ids, snapshot_metadata=version.snapshot_metadata,
        status=version.status.value if hasattr(version.status, 'value') else version.status,
        created_at=version.created_at, updated_at=version.updated_at,
    )


def list_knowledge_versions_to_response(version) -> ListKnowledgeVersionsResponse:
    return ListKnowledgeVersionsResponse(
        id=version.id, version=version.version,
        status=version.status.value if hasattr(version.status, 'value') else version.status,
        created_at=version.created_at,
    )


def chunk_output_to_response(output: DocumentChunkOutput) -> ChunkResponse:
    return ChunkResponse(
        id=output.id,
        content=output.content,
        chunk_index=output.chunk_index,
        token_count=output.token_count,
        page_number=output.page_number,
        section_title=output.section_title,
        data=output.data,
        score=output.similarity,
    )
