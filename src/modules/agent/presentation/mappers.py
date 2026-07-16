from typing import Any

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


def _value(value: Any) -> Any:
    return getattr(value, "value", value)


def credential_to_response(credential: Any) -> ProviderCredentialResponse:
    return ProviderCredentialResponse(
        id=credential.id,
        project_id=credential.project_id,
        provider=_value(credential.provider),
        name=credential.name,
        status=_value(credential.status),
        created_at=credential.created_at,
        metadata=credential.metadata,
    )


def agent_to_response(agent: Any) -> AgentResponse:
    return AgentResponse(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        provider=_value(agent.provider),
        model=agent.model,
        provider_credential_id=agent.provider_credential_id,
        fallback_credential_id=agent.fallback_credential_id,
        fallback_provider=_value(agent.fallback_provider),
        fallback_model=agent.fallback_model,
        temperature=agent.temperature,
        max_output_tokens=agent.max_output_tokens,
        session_mode=_value(agent.session_mode),
        system_prompt=agent.system_prompt,
        description=agent.description,
        status=_value(agent.status),
        settings=agent.settings,
        created_at=agent.created_at,
        updated_at=agent.updated_at,
    )


def prompt_to_response(prompt: Any) -> PromptResponse:
    return PromptResponse(
        id=prompt.id,
        project_id=prompt.project_id,
        agent_id=prompt.agent_id,
        version=prompt.version,
        name=prompt.name,
        content=prompt.content,
        status=_value(prompt.status),
        content_hash=prompt.content_hash,
        created_at=prompt.created_at,
        updated_at=prompt.updated_at,
    )


def list_prompts_to_response(prompt: Any) -> ListPromptsResponse:
    return ListPromptsResponse(
        id=prompt.id,
        version=prompt.version,
        name=prompt.name,
        status=_value(prompt.status),
        created_at=prompt.created_at,
    )


def contract_to_response(contract: Any) -> ContractResponse:
    return ContractResponse(
        id=contract.id,
        project_id=contract.project_id,
        agent_id=contract.agent_id,
        version=contract.version,
        name=contract.name,
        input_schema=contract.input_schema,
        output_schema=contract.output_schema,
        validation_mode=_value(contract.validation_mode),
        repair_attempts=contract.repair_attempts,
        additional_instructions=contract.additional_instructions,
        status=_value(contract.status),
        created_at=contract.created_at,
        updated_at=contract.updated_at,
    )


def list_contracts_to_response(contract: Any) -> ListContractsResponse:
    return ListContractsResponse(
        id=contract.id,
        version=contract.version,
        name=contract.name,
        validation_mode=_value(contract.validation_mode),
        status=_value(contract.status),
        created_at=contract.created_at,
    )


def model_config_to_response(config: Any) -> ModelConfigResponse:
    return ModelConfigResponse(
        id=config.id,
        project_id=config.project_id,
        agent_id=config.agent_id,
        version=config.version,
        provider=_value(config.provider),
        provider_credential_id=config.provider_credential_id,
        model=config.model,
        base_url=config.base_url,
        temperature=config.temperature,
        max_output_tokens=config.max_output_tokens,
        session_mode=_value(config.session_mode),
        settings=config.settings,
        status=_value(config.status),
        created_at=config.created_at,
        updated_at=config.updated_at,
    )


def list_model_configs_to_response(config: Any) -> ListModelConfigsResponse:
    return ListModelConfigsResponse(
        id=config.id,
        version=config.version,
        provider=_value(config.provider),
        model=config.model,
        status=_value(config.status),
        created_at=config.created_at,
    )


def release_to_response(release: Any) -> ReleaseResponse:
    return ReleaseResponse(
        id=release.id,
        project_id=release.project_id,
        agent_id=release.agent_id,
        version=release.version,
        status=_value(release.status),
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


def list_releases_to_response(release: Any) -> ListReleasesResponse:
    return ListReleasesResponse(
        id=release.id,
        version=release.version,
        status=_value(release.status),
        name=getattr(release, "name", None),
        provider=getattr(release, "provider", None),
        model=getattr(release, "model", None),
        system_prompt=getattr(release, "system_prompt", None),
        output_schema=getattr(release, "output_schema", None),
        risk_score=release.risk_score,
        release_notes=release.release_notes,
        created_at=release.created_at,
        promoted_at=release.promoted_at,
    )


def release_test_to_response(test: Any) -> ReleaseTestResponse:
    return ReleaseTestResponse(
        id=test.id,
        project_id=test.project_id,
        agent_id=test.agent_id,
        release_id=test.release_id,
        contract_version_id=test.contract_version_id,
        input_payload=test.input_payload,
        expected_output=test.expected_output,
        actual_output=test.actual_output,
        status=_value(test.status),
        validation_errors=test.validation_errors,
        latency_ms=test.latency_ms,
        created_at=test.created_at,
        updated_at=test.updated_at,
    )


def list_release_tests_to_response(test: Any) -> ListReleaseTestsResponse:
    return ListReleaseTestsResponse(
        id=test.id,
        release_id=test.release_id,
        contract_version_id=test.contract_version_id,
        status=_value(test.status),
        latency_ms=test.latency_ms,
        created_at=test.created_at,
    )


def collection_to_response(collection: Any) -> CollectionResponse:
    return CollectionResponse(
        id=collection.id,
        project_id=collection.project_id,
        name=collection.name,
        description=collection.description,
        status=collection.status,
        created_at=collection.created_at,
        updated_at=collection.updated_at,
    )


def create_collection_output_to_response(output: Any) -> CollectionResponse:
    return collection_to_response(output)


def agent_collection_output_to_response(output: Any) -> AgentCollectionResponse:
    return AgentCollectionResponse(
        id=output.id,
        agent_id=output.agent_id,
        collection_id=output.collection_id,
        created_at=output.created_at,
        updated_at=output.updated_at,
    )


def attach_collection_output_to_response(output: Any) -> AgentCollectionResponse:
    return agent_collection_output_to_response(output)


def document_to_response(document: Any) -> DocumentResponse:
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


def upload_document_output_to_response(output: Any) -> DocumentResponse:
    return document_to_response(output)


def knowledge_version_to_response(version: Any) -> KnowledgeVersionResponse:
    return KnowledgeVersionResponse(
        id=version.id,
        project_id=version.project_id,
        agent_id=version.agent_id,
        version=version.version,
        collection_ids=version.collection_ids or [],
        document_ids=version.document_ids,
        snapshot_metadata=version.snapshot_metadata,
        status=_value(version.status),
        created_at=version.created_at,
        updated_at=version.updated_at,
    )


def list_knowledge_versions_to_response(version: Any) -> ListKnowledgeVersionsResponse:
    return ListKnowledgeVersionsResponse(
        id=version.id,
        version=version.version,
        status=_value(version.status),
        created_at=version.created_at,
    )


def chunk_output_to_response(output: Any) -> ChunkResponse:
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
