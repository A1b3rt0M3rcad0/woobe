from fastapi import APIRouter, Request

from modules.agent.entrypoint import skill_catalog_composer
from woobe_api.http.shared.adapters import request_adapter, response_adapter

router = APIRouter(prefix="/ai/projects/{project_id}/skills", tags=["ai", "skills"])


async def _handle(request: Request, operation: str):
    return response_adapter(
        await request_adapter(
            request,
            skill_catalog_composer(),
            metadata={"skill_operation": operation},
        )
    )


@router.get("")
async def list_skills(request: Request):
    return await _handle(request, "list")


@router.post("", status_code=201)
async def create_skill(request: Request):
    return await _handle(request, "create")


@router.get("/versions/{skill_version_id}")
async def get_skill_version(request: Request):
    return await _handle(request, "get_version")


@router.get("/{skill_id}/versions")
async def list_skill_versions(request: Request):
    return await _handle(request, "versions")


@router.post("/{skill_id}/versions", status_code=201)
async def create_skill_version(request: Request):
    return await _handle(request, "add_version")
