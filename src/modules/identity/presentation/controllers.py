from uuid import UUID

from fastapi import APIRouter, Depends

from modules.identity.application.providers import (
    get_add_member_use_case,
    get_create_organization_use_case,
    get_create_user_use_case,
    get_user_by_id_use_case,
)
from modules.identity.presentation.schemas import (
    AddMemberRequest,
    CreateOrganizationRequest,
    CreateUserRequest,
    MemberResponse,
    OrganizationResponse,
    UserResponse,
)
from modules.identity.service.dtos import (
    AddMemberInput,
    CreateOrganizationInput,
    CreateUserInput,
)
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/identity", tags=["identity"])


@router.post("/users")
async def create_user(
    request: CreateUserRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_create_user_use_case(manager.session)
    input_dto = CreateUserInput(email=request.email, password=request.password)
    result = await use_case.execute(input_dto)
    return created(UserResponse(**result.model_dump()))


@router.post("/organizations")
async def create_organization(
    request: CreateOrganizationRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_create_organization_use_case(manager.session)
    input_dto = CreateOrganizationInput(
        name=request.name, slug=request.slug
    )
    result = await use_case.execute(input_dto)
    return created(OrganizationResponse(**result.model_dump()))


@router.post("/organizations/{org_id}/members")
async def add_member(
    org_id: UUID,
    request: AddMemberRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_add_member_use_case(manager.session)
    input_dto = AddMemberInput(
        user_id=request.user_id,
        organization_id=org_id,
        role=request.role,
    )
    result = await use_case.execute(input_dto)
    return created(MemberResponse(**result.model_dump()))


@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = get_user_by_id_use_case(manager.session)
    result = await use_case.execute(user_id)
    return ok(UserResponse(**result.model_dump()))
