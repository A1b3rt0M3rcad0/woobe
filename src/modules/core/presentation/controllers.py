from uuid import UUID

from fastapi import APIRouter, Depends

from modules.core.application.dependencies import get_current_user_id
from modules.core.application.providers import (
    get_create_api_key_use_case,
    get_create_project_use_case,
    get_project_by_id_use_case,
    list_api_keys_by_project_use_case,
)
from modules.core.presentation.schemas import (
    ApiKeyResponse,
    CreateApiKeyRequest,
    CreateProjectRequest,
    ProjectResponse,
)
from modules.core.service.dtos import (
    CreateApiKeyInput,
    CreateProjectInput,
)
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/core", tags=["core"])


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
    return ok(ProjectResponse(**result.model_dump()))


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
    return created(ApiKeyResponse(**result.model_dump()))


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(
    project_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = list_api_keys_by_project_use_case(manager.session)
    result = await use_case.execute(project_id)
    return ok([ApiKeyResponse(**item.model_dump()) for item in result])
