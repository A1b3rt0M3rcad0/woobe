from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
    UserSession,
)
from modules.identity.domain.enums import (
    InviteStatus,
    MemberRole,
    MemberStatus,
    WorkspaceStatus,
    UserSessionStatus,
    UserStatus,
)
from modules.identity.infra.database.models import (
    WorkspaceInviteModel,
    WorkspaceMemberModel,
    WorkspaceModel,
    UserModel,
    UserSessionModel,
)


def user_model_to_entity(model: UserModel) -> User:
    return User(
        id=model.id,
        email=model.email,
        password=model.password,
        status=UserStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_entity_to_model(entity: User) -> UserModel:
    return UserModel(
        id=entity.id,
        email=entity.email,
        password=entity.password,
        status=entity.status.value,
    )


def workspace_model_to_entity(model: WorkspaceModel) -> Workspace:
    return Workspace(
        id=model.id,
        name=model.name,
        slug=model.slug,
        status=WorkspaceStatus(model.status),
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def workspace_entity_to_model(entity: Workspace) -> WorkspaceModel:
    return WorkspaceModel(
        id=entity.id,
        name=entity.name,
        slug=entity.slug,
        status=entity.status.value,
    )


def workspace_member_model_to_entity(
    model: WorkspaceMemberModel,
) -> WorkspaceMember:
    return WorkspaceMember(
        id=model.id,
        user_id=model.user_id,
        workspace_id=model.workspace_id,
        role=MemberRole(model.role),
        status=MemberStatus(model.status),
        joined_at=model.joined_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def workspace_member_entity_to_model(
    entity: WorkspaceMember,
) -> WorkspaceMemberModel:
    return WorkspaceMemberModel(
        id=entity.id,
        user_id=entity.user_id,
        workspace_id=entity.workspace_id,
        role=entity.role.value,
        status=entity.status.value,
        joined_at=entity.joined_at,
    )


def workspace_invite_model_to_entity(
    model: WorkspaceInviteModel,
) -> WorkspaceInvite:
    return WorkspaceInvite(
        id=model.id,
        workspace_id=model.workspace_id,
        email=model.email,
        role=MemberRole(model.role),
        token_hash=model.token_hash,
        invited_by_user_id=model.invited_by_user_id,
        status=InviteStatus(model.status),
        expires_at=model.expires_at,
        accepted_at=model.accepted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def workspace_invite_entity_to_model(
    entity: WorkspaceInvite,
) -> WorkspaceInviteModel:
    return WorkspaceInviteModel(
        id=entity.id,
        workspace_id=entity.workspace_id,
        email=entity.email,
        role=entity.role.value,
        token_hash=entity.token_hash,
        invited_by_user_id=entity.invited_by_user_id,
        status=entity.status.value,
        expires_at=entity.expires_at,
        accepted_at=entity.accepted_at,
    )


def user_session_model_to_entity(model: UserSessionModel) -> UserSession:
    if model.revoked_at is not None:
        status = UserSessionStatus.revoked
    else:
        status = UserSessionStatus.active
    return UserSession(
        id=model.id,
        user_id=model.user_id,
        refresh_token_hash=model.refresh_token_hash,
        user_agent=model.user_agent,
        ip_address=model.ip_address,
        status=status,
        revoked_at=model.revoked_at,
        expires_at=model.expires_at,
        last_used_at=model.last_used_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_session_entity_to_model(entity: UserSession) -> UserSessionModel:
    return UserSessionModel(
        id=entity.id,
        user_id=entity.user_id,
        refresh_token_hash=entity.refresh_token_hash,
        user_agent=entity.user_agent,
        ip_address=entity.ip_address,
        revoked_at=entity.revoked_at,
        expires_at=entity.expires_at,
        last_used_at=entity.last_used_at,
    )
