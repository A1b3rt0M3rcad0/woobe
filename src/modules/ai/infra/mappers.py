from modules.ai.domain.entities import Agent, ProviderCredential
from modules.ai.domain.enums import (
    AgentStatus,
    AgentType,
    CredentialStatus,
    Provider,
    SessionMode,
)
from modules.ai.infra.models import AgentModel, ProviderCredentialModel


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
