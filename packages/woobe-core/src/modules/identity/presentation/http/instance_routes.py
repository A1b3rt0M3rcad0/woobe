from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.dtos import RegisterInput
from modules.identity.application.instance_service import InstanceService
from modules.identity.presentation.authentication_response import (
    AuthenticationCookiePolicy,
    authentication_response,
)
from shared.presentation.http.adapter import response_adapter
from shared.presentation.http.request import Request


router = APIRouter(prefix="/identity/instance", tags=["instance"])


def instance_service(request: FastAPIRequest) -> InstanceService:
    return InstanceService(
        request.app.state.session_factory,
        request.app.state.access_token_codec,
        request.app.state.settings,
    )


def _cookie_policy(request: FastAPIRequest) -> AuthenticationCookiePolicy:
    settings = request.app.state.settings
    return AuthenticationCookiePolicy(
        access_cookie_name=settings.access_cookie_name,
        access_cookie_secure=settings.access_cookie_secure,
        access_cookie_same_site=settings.access_cookie_same_site,
        refresh_cookie_name=settings.refresh_cookie_name,
        refresh_cookie_secure=settings.refresh_cookie_secure,
        refresh_cookie_same_site=settings.refresh_cookie_same_site,
        csrf_cookie_name=settings.csrf_cookie_name,
        refresh_token_ttl_days=settings.refresh_token_ttl_days,
        access_token_ttl_seconds=settings.access_token_ttl_seconds,
    )


def _request(request: FastAPIRequest) -> Request:
    return Request(
        url=str(request.url),
        method=request.method,
        headers=dict(request.headers),
        cookies=dict(request.cookies),
        client_ip=request.client.host if request.client else None,
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
    response = authentication_response(
        _request(request),
        result,
        _cookie_policy(request),
        status_code=201,
    )
    return response_adapter(response)
