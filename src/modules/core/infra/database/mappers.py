from modules.core.domain.entities import ApiKey, Project
from modules.core.domain.enums import ApiKeyStatus, ProjectStatus
from modules.core.infra.database.models import ApiKeyModel, ProjectModel


def project_model_to_entity(model: ProjectModel) -> Project:
    return Project(
        id=model.id,
        organization_id=model.organization_id,
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
        organization_id=entity.organization_id,
        name=entity.name,
        slug=entity.slug,
        status=entity.status.value,
        data=entity.data,
    )


def api_key_model_to_entity(model: ApiKeyModel) -> ApiKey:
    return ApiKey(
        id=model.id,
        project_id=model.project_id,
        name=model.name,
        key_prefix=model.key_prefix,
        key_hash=model.key_hash,
        scopes=model.scopes,
        status=ApiKeyStatus(model.status),
        last_used_at=model.last_used_at,
        expires_at=model.expires_at,
        revoked_at=model.revoked_at,
        created_by_user_id=model.created_by_user_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def api_key_entity_to_model(entity: ApiKey) -> ApiKeyModel:
    return ApiKeyModel(
        id=entity.id,
        project_id=entity.project_id,
        name=entity.name,
        key_prefix=entity.key_prefix,
        key_hash=entity.key_hash,
        scopes=entity.scopes,
        status=entity.status.value,
        last_used_at=entity.last_used_at,
        expires_at=entity.expires_at,
        revoked_at=entity.revoked_at,
        created_by_user_id=entity.created_by_user_id,
    )
