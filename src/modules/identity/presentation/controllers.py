import base64

from fastapi import APIRouter, Depends
from sqlalchemy import select
from uuid import UUID

from modules.identity.application.providers import (
    get_add_member_use_case,
    get_create_organization_use_case,
    get_create_user_use_case,
    get_invite_repo,
    get_member_repo,
    get_organization_repo,
    get_update_organization_use_case,
    get_user_by_id_use_case,
)
from modules.identity.infra.models import UserModel
from modules.identity.infra.repositories import (
    SQLAlchemyOrganizationRepository,
    SQLAlchemyUserRepository,
)
from modules.identity.presentation.schemas import (
    AddMemberRequest,
    CreateOrganizationRequest,
    CreateUserRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    LoginResponse,
    MemberResponse,
    OrganizationResponse,
    RegisterRequest,
    UpdateOrganizationRequest,
    UserResponse,
)
from modules.identity.service.dtos import (
    AddMemberInput,
    CreateOrganizationInput,
    CreateUserInput,
    InviteUserInput,
    UpdateOrganizationInput,
)
from modules.identity.service.use_cases import InviteUserUseCase
from shared.infra.crypto import verify_password
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/identity", tags=["identity"])


@router.get("/organizations")
async def list_organizations(
    manager=Depends(get_session_manager),
):
    repo = SQLAlchemyOrganizationRepository(manager.session)
    orgs = await repo.list_all()
    return ok([OrganizationResponse(
        id=o.id,
        name=o.name,
        slug=o.slug,
        status=o.status,
        created_at=o.created_at,
    ) for o in orgs])


@router.get("/users/me")
async def get_current_user(
    manager=Depends(get_session_manager),
):
    return ok({"email": "customer@gmail.com", "name": None})


@router.post("/auth/login")
async def login(
    request: LoginRequest,
    manager=Depends(get_session_manager),
):
    repo = SQLAlchemyUserRepository(manager.session)
    user = await repo.get_by_email(request.email)
    if not user or not verify_password(request.password, user.password):
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=401,
            content={"success": False, "message": "Invalid credentials", "data": None},
        )
    token = base64.b64encode(str(user.id).encode()).decode()
    return ok(
        data=LoginResponse(
            token=token,
            user={"id": str(user.id), "email": user.email},
        ).model_dump()
    )


@router.post("/auth/register")
async def register(
    request: RegisterRequest,
    manager=Depends(get_session_manager),
):
    uc_user = get_create_user_use_case(manager.session)
    user = await uc_user.execute(CreateUserInput(email=request.email, password=request.password))

    uc_org = get_create_organization_use_case(manager.session)
    org = await uc_org.execute(CreateOrganizationInput(name=request.organization_name, slug=request.organization_name.lower().replace(" ", "-")))

    uc_member = get_add_member_use_case(manager.session)
    await uc_member.execute(AddMemberInput(user_id=user.id, organization_id=org.id, role="owner"))

    token = base64.b64encode(str(user.id).encode()).decode()
    return created(
        data=LoginResponse(
            token=token,
            user={"id": str(user.id), "email": user.email},
        ).model_dump()
    )


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


@router.get("/organizations/{org_id}")
async def get_organization(
    org_id: UUID,
    manager=Depends(get_session_manager),
):
    repo = get_organization_repo(manager.session)
    org = await repo.get_by_id(org_id)
    if not org:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=404,
            content={"success": False, "message": "Organization not found", "data": None},
        )
    return ok(OrganizationResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        status=org.status,
        created_at=org.created_at,
    ))


@router.patch("/organizations/{org_id}")
async def update_organization(
    org_id: UUID,
    request: UpdateOrganizationRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_update_organization_use_case(manager.session)
    input_dto = UpdateOrganizationInput(
        name=request.name,
        slug=request.slug,
    )
    result = await use_case.execute(org_id, input_dto)
    return ok(OrganizationResponse(
        id=result.id,
        name=result.name,
        slug=result.slug,
        status=result.status,
        created_at=result.created_at,
    ))


@router.get("/organizations/{org_id}/members")
async def list_members(
    org_id: UUID,
    manager=Depends(get_session_manager),
):
    repo = get_member_repo(manager.session)
    members = await repo.list_by_organization(org_id)
    return ok([MemberResponse(
        id=m.id,
        user_id=m.user_id,
        organization_id=m.organization_id,
        role=m.role.value if hasattr(m.role, 'value') else m.role,
        status=m.status.value if hasattr(m.status, 'value') else m.status,
    ) for m in members])


@router.post("/organizations/{org_id}/invites")
async def create_invite(
    org_id: UUID,
    request: InviteRequest,
    manager=Depends(get_session_manager),
):
    from modules.identity.infra.repositories import SQLAlchemyOutboxEventWriter
    use_case = InviteUserUseCase(
        get_organization_repo(manager.session),
        get_invite_repo(manager.session),
        SQLAlchemyOutboxEventWriter(manager.session),
    )
    input_dto = InviteUserInput(
        organization_id=org_id,
        email=request.email,
        role=request.role,
        invited_by_user_id=UUID("00000000-0000-0000-0000-000000000001"),
    )
    result = await use_case.execute(input_dto)
    return created(InviteResponse(
        id=result.id,
        organization_id=result.organization_id,
        email=result.email,
        role=result.role.value if hasattr(result.role, 'value') else result.role,
        status=result.status.value if hasattr(result.status, 'value') else result.status,
        expires_at=result.expires_at,
        created_at=result.created_at,
    ))


@router.get("/organizations/{org_id}/invites")
async def list_invites(
    org_id: UUID,
    manager=Depends(get_session_manager),
):
    repo = get_invite_repo(manager.session)
    invites = await repo.list_by_organization(org_id)
    return ok([InviteResponse(
        id=i.id,
        organization_id=i.organization_id,
        email=i.email,
        role=i.role.value if hasattr(i.role, 'value') else i.role,
        status=i.status.value if hasattr(i.status, 'value') else i.status,
        expires_at=i.expires_at,
        created_at=i.created_at,
    ) for i in invites])


@router.get("/users/{user_id}")
async def get_user(
    user_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = get_user_by_id_use_case(manager.session)
    result = await use_case.execute(user_id)
    return ok(UserResponse(
        id=result.id,
        email=result.email,
        status=result.status.value if hasattr(result.status, 'value') else result.status,
        created_at=result.created_at,
    ))
