from fastapi import APIRouter, Request as FastAPIRequest

from modules.core.application.composers.create_api_key_composer import (
    create_api_key_composer,
)
from modules.core.application.composers.create_project_composer import (
    create_project_composer,
)
from modules.core.application.composers.create_runtime_api_key_composer import (
    create_runtime_api_key_composer,
)
from modules.core.application.composers.get_project_composer import get_project_composer
from modules.core.application.composers.get_project_overview_composer import (
    get_project_overview_composer,
)
from modules.core.application.composers.list_api_keys_composer import (
    list_api_keys_composer,
)
from modules.core.application.composers.list_projects_composer import (
    list_projects_composer,
)
from modules.core.application.composers.revoke_api_key_composer import (
    revoke_api_key_composer,
)
from modules.core.application.composers.rotate_api_key_composer import (
    rotate_api_key_composer,
)
from modules.core.application.composers.update_project_composer import (
    update_project_composer,
)
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/core", tags=["core"])


@router.get("/projects")
async def list_projects(request: FastAPIRequest):
    handler = list_projects_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects")
async def create_project(request: FastAPIRequest):
    handler = create_project_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/overview")
async def get_project_overview(request: FastAPIRequest):
    handler = get_project_overview_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}")
async def get_project(request: FastAPIRequest):
    handler = get_project_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/projects/{project_id}")
async def update_project(request: FastAPIRequest):
    handler = update_project_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/api-keys")
async def create_api_key(request: FastAPIRequest):
    handler = create_api_key_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/runtime-keys", status_code=201)
async def create_runtime_api_key(request: FastAPIRequest):
    handler = create_runtime_api_key_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/projects/{project_id}/api-keys")
async def list_api_keys(request: FastAPIRequest):
    handler = list_api_keys_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/api-keys/{api_key_id}/revoke")
async def revoke_api_key(request: FastAPIRequest):
    handler = revoke_api_key_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/projects/{project_id}/api-keys/{api_key_id}/rotate", status_code=201)
async def rotate_api_key(request: FastAPIRequest):
    handler = rotate_api_key_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
