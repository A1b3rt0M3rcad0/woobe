from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.dtos import RegisterInput
from modules.identity.application.instance_service import InstanceService
from modules.identity.presentation.auth_endpoints import authentication_response


router = APIRouter(prefix="/identity/instance", tags=["instance"])


def instance_service(request: FastAPIRequest) -> InstanceService:
    return InstanceService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


@router.get("/status")
async def instance_status(request: FastAPIRequest):
    return {
        "success": True,
        "message": "ok",
        "data": await instance_service(request).status(),
    }


@router.post("/bootstrap", status_code=201)
async def bootstrap_instance(request: FastAPIRequest):
    data = RegisterInput(**(await request.json()))
    result = await instance_service(request).bootstrap(
        email=data.email,
        password=data.password,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    return authentication_response(request, result, status_code=201)
