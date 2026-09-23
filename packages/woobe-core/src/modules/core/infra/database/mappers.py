from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.enums import (
    ApiKeyKind,
    ApiKeyStatus,
    ProjectStatus,
    RuntimeEnvironment,
    RuntimeTargetType,
)
from modules.core.infra.database.models import ApiKeyModel, ProjectModel


def project_model_to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        workspace_id=model.workspace_id,
        name=model.name,
        slug=model.slug,
        status=ProjectStatus(model.status),
        data=model.data,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def project_entity_to_model(entity: Project) -> ProjectModel:
    return ProjectModel(
        id=entity.id,
        workspace_id=entity.workspace_id,
        name=entity.name,
        slug=entity.slug,
        status=entity.status.value,
        data=entity.data,
    )


def api_key_model_to_entity(model: ApiKeyModel) -> ApiKey:
    return ApiKey(
        id=model.id,
        project_id=model.project_id,
        credential_id=model.credential_id,
        name=model.name,
        description=model.description,
        key_prefix=model.key_prefix,
        key_hash=model.key_hash,
        key_version=model.key_version,
        scopes=model.scopes,
        kind=ApiKeyKind(model.kind),
        agent_id=model.agent_id,
        target_type=(
            RuntimeTargetType(model.target_type)
            if model.target_type
            else RuntimeTargetType.agent
            if model.agent_id
            else None
        ),
        target_id=model.target_id or model.agent_id,
        environment=RuntimeEnvironment(model.environment)
        if model.environment
        else None,
        interfaces=list(model.interfaces or []),
        status=ApiKeyStatus(model.status),
        last_used_at=model.last_used_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_by_user_id=model.created_by_user_id,
        created_by_control_key_id=model.created_by_control_key_id,
        rotated_from_id=model.rotated_from_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def api_key_entity_to_model(entity: ApiKey) -> ApiKeyModel:
    return ApiKeyModel(
        id=entity.id,
        project_id=entity.project_id,
        credential_id=entity.credential_id or entity.id,
        name=entity.name,
        description=entity.description,
        key_prefix=entity.key_prefix,
        key_hash=entity.key_hash,
        key_version=entity.key_version,
        scopes=entity.scopes,
        kind=entity.kind.value,
        agent_id=entity.agent_id,
        target_type=entity.target_type.value if entity.target_type else None,
        target_id=entity.target_id,
        environment=entity.environment.value if entity.environment else None,
        interfaces=entity.interfaces,
        status=entity.status.value,
        last_used_at=entity.last_used_at,
        expires_at=entity.expires_at,
        revoked_at=entity.revoked_at,
        created_by_user_id=entity.created_by_user_id,
        created_by_control_key_id=entity.created_by_control_key_id,
        rotated_from_id=entity.rotated_from_id,
    )
