from modules.agent.entrypoint import ImportSkillInput, SkillListQuery
from woobe_api.http.shared.openapi_contracts import request_body_contract, query_parameter_contract
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


@router.get("", openapi_extra=query_parameter_contract(SkillListQuery, "/ai/projects/{project_id}/skills"))
async def list_skills(request: Request):
    return await _handle(request, "list")


@router.post("", status_code=201, openapi_extra=request_body_contract(ImportSkillInput, "/ai/projects/{project_id}/skills", "post"))
async def create_skill(request: Request):
    return await _handle(request, "create")


@router.get("/versions/{skill_version_id}")
async def get_skill_version(request: Request):
    return await _handle(request, "get_version")


@router.get("/{skill_id}/versions", openapi_extra=query_parameter_contract(SkillListQuery, "/ai/projects/{project_id}/skills/{skill_id}/versions", query_fields=("offset", "limit")))
async def list_skill_versions(request: Request):
    return await _handle(request, "versions")


@router.post("/{skill_id}/versions", status_code=201, openapi_extra=request_body_contract(ImportSkillInput, "/ai/projects/{project_id}/skills/{skill_id}/versions", "post"))
async def create_skill_version(request: Request):
    return await _handle(request, "add_version")
