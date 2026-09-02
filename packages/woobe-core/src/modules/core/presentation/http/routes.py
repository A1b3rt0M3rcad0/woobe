from fastapi import APIRouter, Request as FastAPIRequest

from modules.core.composition.composers.create_api_key_composer import (
    create_api_key_composer,
)
from modules.core.composition.composers.create_project_composer import (
    create_project_composer,
)
from modules.core.composition.composers.create_runtime_api_key_composer import (
    create_runtime_api_key_composer,
)
from modules.core.composition.composers.get_project_composer import (
    get_project_composer,
)
from modules.core.composition.composers.get_project_overview_composer import (
    get_project_overview_composer,
)
from modules.core.composition.composers.list_api_keys_composer import (
    list_api_keys_composer,
)
from modules.core.composition.composers.project_access_composers import (
    grant_project_access_composer,
    grant_project_subject_access_composer,
    list_accessible_projects_composer,
    list_project_members_composer,
    list_projects_for_access_management_composer,
    revoke_project_access_composer,
    revoke_project_subject_access_composer,
)
from modules.core.composition.composers.revoke_api_key_composer import (
    revoke_api_key_composer,
)
from modules.core.composition.composers.rotate_api_key_composer import (
    rotate_api_key_composer,
)
from modules.core.composition.composers.update_api_key_credential_composer import (
    update_api_key_credential_composer,
)
from modules.core.composition.composers.update_project_composer import (
    update_project_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/core", tags=["core"])


async def _handle(request: FastAPIRequest, handler):
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects")
async def list_projects(request: FastAPIRequest):
    return await _handle(request, list_accessible_projects_composer())


@router.post("/projects")
async def create_project(request: FastAPIRequest):
    return await _handle(request, create_project_composer())


@router.get("/workspaces/{workspace_id}/project-access")
async def list_projects_for_access_management(request: FastAPIRequest):
    return await _handle(
        request,
        list_projects_for_access_management_composer(),
    )


@router.get("/projects/{access_project_id}/members")
async def list_project_members(request: FastAPIRequest):
    return await _handle(request, list_project_members_composer())


@router.post("/projects/{access_project_id}/access", status_code=201)
async def grant_project_subject_access(request: FastAPIRequest):
    return await _handle(request, grant_project_subject_access_composer())


@router.delete("/projects/{access_project_id}/access/{subject_type}/{subject_id}")
async def revoke_project_subject_access(request: FastAPIRequest):
    return await _handle(request, revoke_project_subject_access_composer())


@router.post("/projects/{access_project_id}/members", status_code=201)
async def grant_project_access(request: FastAPIRequest):
    return await _handle(request, grant_project_access_composer())


@router.delete("/projects/{access_project_id}/members/{target_user_id}")
async def revoke_project_access(request: FastAPIRequest):
    return await _handle(request, revoke_project_access_composer())


@router.get("/projects/{project_id}/overview")
async def get_project_overview(request: FastAPIRequest):
    return await _handle(request, get_project_overview_composer())


@router.get("/projects/{project_id}")
async def get_project(request: FastAPIRequest):
    return await _handle(request, get_project_composer())


@router.patch("/projects/{project_id}")
async def update_project(request: FastAPIRequest):
    return await _handle(request, update_project_composer())


@router.post("/projects/{project_id}/api-keys")
async def create_api_key(request: FastAPIRequest):
    return await _handle(request, create_api_key_composer())


@router.post("/projects/{project_id}/runtime-keys", status_code=201)
async def create_runtime_api_key(request: FastAPIRequest):
    return await _handle(request, create_runtime_api_key_composer())


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(request: FastAPIRequest):
    return await _handle(request, list_api_keys_composer())


@router.post("/projects/{project_id}/api-keys/{api_key_id}/revoke")
async def revoke_api_key(request: FastAPIRequest):
    return await _handle(request, revoke_api_key_composer())


@router.post("/projects/{project_id}/api-keys/{api_key_id}/rotate", status_code=201)
async def rotate_api_key(request: FastAPIRequest):
    return await _handle(request, rotate_api_key_composer())


@router.patch("/projects/{project_id}/api-keys/{api_key_id}")
async def update_api_key_credential(request: FastAPIRequest):
    return await _handle(request, update_api_key_credential_composer())
