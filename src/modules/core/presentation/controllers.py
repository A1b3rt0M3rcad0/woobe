from uuid import UUID

from fastapi import APIRouter, Depends, Query

from modules.core.application.dependencies import get_current_user_id
from modules.core.application.providers import (
    get_create_api_key_use_case,
    get_create_project_use_case,
    get_project_by_id_use_case,
    list_api_keys_by_project_use_case,
    list_projects_use_case,
)
from modules.core.presentation.mappers import (
    api_key_to_response,
    project_to_response,
)
from modules.core.presentation.schemas import (
    CreateApiKeyRequest,
    CreateProjectRequest,
    UpdateProjectRequest,
)
from modules.core.service.dtos import (
    CreateApiKeyInput,
    CreateProjectInput,
)
from modules.core.infra.repositories import SQLAlchemyProjectRepository
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/core", tags=["core"])


@router.get("/projects")
async def list_projects(
    organization_id: UUID | None = Query(None),
    manager=Depends(get_session_manager),
):
    use_case = list_projects_use_case(manager.session)
    result = await use_case.execute(organization_id)
    return ok([project_to_response(item) for item in result])


@router.post("/projects")
async def create_project(
    request: CreateProjectRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_create_project_use_case(manager.session)
    input_dto = CreateProjectInput(
        organization_id=request.organization_id,
        name=request.name,
        slug=request.slug,
    )
    result = await use_case.execute(input_dto)
    return created(ProjectResponse(**result.model_dump()))


@router.get("/projects/{project_id}")
async def get_project(
    project_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = get_project_by_id_use_case(manager.session)
    result = await use_case.execute(project_id)
    return ok(project_to_response(result))


@router.patch("/projects/{project_id}")
async def update_project(
    project_id: UUID,
    request: UpdateProjectRequest,
    manager=Depends(get_session_manager),
):
    repo = SQLAlchemyProjectRepository(manager.session)
    project = await repo.get_by_id(project_id)
    if not project:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Project not found", "data": None},
        )
    if request.name is not None:
        project.name = request.name
    if request.slug is not None:
        project.slug = request.slug
    from datetime import UTC, datetime
    project.updated_at = datetime.now(UTC)
    saved = await repo.save(project)
    return ok(ProjectResponse(
        id=saved.id,
        organization_id=saved.organization_id,
        name=saved.name,
        slug=saved.slug,
        status=saved.status.value if hasattr(saved.status, 'value') else saved.status,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    ))


@router.post("/projects/{project_id}/api-keys")
async def create_api_key(
    project_id: UUID,
    request: CreateApiKeyRequest,
    manager=Depends(get_session_manager),
    user_id: UUID = Depends(get_current_user_id),
):
    use_case = get_create_api_key_use_case(manager.session)
    input_dto = CreateApiKeyInput(
        project_id=project_id,
        name=request.name,
        scopes=request.scopes,
        created_by_user_id=user_id,
    )
    result = await use_case.execute(input_dto)
    return created(ApiKeyResponse(
        id=result.id,
        name=result.name,
        key_prefix=result.key_prefix,
        status=result.status.value if hasattr(result.status, 'value') else result.status,
    ))


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(
    project_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = list_api_keys_by_project_use_case(manager.session)
    result = await use_case.execute(project_id)
    return ok([api_key_to_response(item) for item in result])
