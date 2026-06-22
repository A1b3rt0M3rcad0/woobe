import re
import unicodedata
from datetime import UTC, datetime

from fastapi import APIRouter, Request as FastAPIRequest

from modules.identity.application.composers.add_member_composer import add_member_composer
from modules.identity.application.composers.create_invite_composer import (
    create_invite_composer,
)
from modules.identity.application.composers.create_organization_composer import (
    create_organization_composer,
)
from modules.identity.application.composers.create_user_composer import create_user_composer
from modules.identity.application.composers.get_organization_composer import (
    get_organization_composer,
)
from modules.identity.application.composers.get_user_composer import get_user_composer
from modules.identity.application.composers.list_invites_composer import (
    list_invites_composer,
)
from modules.identity.application.composers.list_members_composer import list_members_composer
from modules.identity.application.composers.update_organization_composer import (
    update_organization_composer,
)
from modules.identity.domain.entities import OrganizationMember
from modules.identity.domain.enums import MemberRole
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.auth_endpoints import (
    get_current_user_endpoint,
    list_organizations_endpoint,
    login_endpoint,
    logout_endpoint,
    refresh_endpoint,
    register_endpoint,
)
from shared.infra.errors import AuthenticationError
from shared.presentation.http.adapter import request_adapter, response_adapter

router = APIRouter(prefix="/identity", tags=["identity"])


def _slugify(value: str, fallback: str = "organization") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")[:128]
    return slug or fallback


@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    return await list_organizations_endpoint(request)


@router.get("/users/me")
async def get_current_user(request: FastAPIRequest):
    return await get_current_user_endpoint(request)


@router.post("/auth/login")
async def login(request: FastAPIRequest):
    return await login_endpoint(request)


@router.post("/auth/register")
async def register(request: FastAPIRequest):
    return await register_endpoint(request)


@router.post("/auth/refresh")
async def refresh(request: FastAPIRequest):
    return await refresh_endpoint(request)


@router.post("/auth/logout")
async def logout(request: FastAPIRequest):
    return await logout_endpoint(request)


@router.post("/users")
async def create_user(request: FastAPIRequest):
    handler = create_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations")
async def create_organization(request: FastAPIRequest):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")

    payload = dict(await request.json())
    payload["name"] = str(payload.get("name", "")).strip()
    payload["slug"] = _slugify(str(payload.get("slug") or payload.get("name") or "organization"))
    request.state.body_override = payload

    handler = create_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)

    if 200 <= response.status_code < 300:
        organization_id = response.body.get("data", {}).get("id")
        if organization_id:
            async with IdentityUnitOfWork(request.app.state.session_factory) as uow:
                existing_member = await uow.members.get_by_organization_and_user(
                    organization_id, principal.user_id
                )
                if existing_member is None:
                    member = OrganizationMember(
                        user_id=principal.user_id,
                        organization_id=organization_id,
                        role=MemberRole.owner,
                        joined_at=datetime.now(UTC),
                    )
                    saved_member = await uow.members.save(member)
                    await uow.outbox.write(
                        aggregate_type="organization_member",
                        aggregate_id=saved_member.id,
                        event_type="organization.member_added.v1",
                        payload={
                            "user_id": str(principal.user_id),
                            "organization_id": str(organization_id),
                            "role": saved_member.role.value,
                        },
                        routing_key="organization.member_added.v1",
                        idempotency_key=f"identity:organization.member_added.v1:{saved_member.id}",
                    )

    return response_adapter(response)


@router.post("/organizations/{org_id}/members")
async def add_member(request: FastAPIRequest):
    handler = add_member_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}")
async def get_organization(request: FastAPIRequest):
    handler = get_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.patch("/organizations/{org_id}")
async def update_organization(request: FastAPIRequest):
    payload = dict(await request.json())
    if payload.get("slug") is not None:
        payload["slug"] = _slugify(str(payload.get("slug") or payload.get("name") or "organization"))
    request.state.body_override = payload

    handler = update_organization_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/members")
async def list_members(request: FastAPIRequest):
    handler = list_members_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.post("/organizations/{org_id}/invites")
async def create_invite(request: FastAPIRequest):
    principal = getattr(request.state, "principal", None)
    if principal is None:
        raise AuthenticationError("Authentication required")
    payload = dict(await request.json())
    payload["invited_by_user_id"] = str(principal.user_id)
    request.state.body_override = payload
    handler = create_invite_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/organizations/{org_id}/invites")
async def list_invites(request: FastAPIRequest):
    handler = list_invites_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)


@router.get("/users/{user_id}")
async def get_user(request: FastAPIRequest):
    handler = get_user_composer(request.app.state.session_factory)
    response = await request_adapter(request, handler)
    return response_adapter(response)
