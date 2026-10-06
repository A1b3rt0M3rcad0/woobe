from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.entrypoint import RegisterInput
from modules.identity.entrypoint import InstanceService, build_instance_service
from woobe_api.http.identity.auth_endpoints import authentication_response
from woobe_api.http.shared.openapi_contracts import request_body_contract


router = APIRouter(prefix="/identity/instance", tags=["instance"])


def instance_service(request: FastAPIRequest) -> InstanceService:
    del request
    return build_instance_service()


@router.get("/status")
async def instance_status(request: FastAPIRequest):
    return {
        "success": True,
        "message": "ok",
        "data": await instance_service(request).status(),
    }


@router.post(
    "/bootstrap",
    status_code=201,
    openapi_extra=request_body_contract(
        RegisterInput, "/identity/instance/bootstrap", "post"
    ),
)
async def bootstrap_instance(request: FastAPIRequest):
    data = RegisterInput(**(await request.json()))
    result = await instance_service(request).bootstrap(
        email=data.email,
        password=data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return authentication_response(request, result, status_code=201)
