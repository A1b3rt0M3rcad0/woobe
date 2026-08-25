from modules.core.domain.entities import ApiKey, Project
from modules.core.presentation.schemas import ApiKeyResponse, ProjectResponse


def project_to_response(project: Project) -> ProjectResponse:
    return ProjectResponse(
        id=project.id,
        workspace_id=project.workspace_id,
        name=project.name,
        slug=project.slug,
        status=project.status.value if hasattr(project.status, 'value') else project.status,
        created_at=project.created_at,
        updated_at=project.updated_at,
    )


def api_key_to_response(api_key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        status=api_key.status.value if hasattr(api_key.status, 'value') else api_key.status,
    )
