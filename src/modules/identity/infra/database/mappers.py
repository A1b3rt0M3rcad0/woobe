from modules.identity.domain.entities import User, UserInvite, UserSession
from modules.identity.domain.enums import InviteStatus, UserSessionStatus, UserStatus
from modules.identity.infra.database.models import UserInviteModel, UserModel, UserSessionModel


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


def user_invite_model_to_entity(model: UserInviteModel) -> UserInvite:
    return UserInvite(
        id=model.id,
        workspace_id=model.workspace_id,
        email=model.email,
        token_hash=model.token_hash,
        invited_by_user_id=model.invited_by_user_id,
        status=InviteStatus(model.status),
        expires_at=model.expires_at,
        accepted_at=model.accepted_at,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def user_invite_entity_to_model(entity: UserInvite) -> UserInviteModel:
    return UserInviteModel(
        id=entity.id,
        workspace_id=entity.workspace_id,
        email=entity.email,
        token_hash=entity.token_hash,
        invited_by_user_id=entity.invited_by_user_id,
        status=entity.status.value,
        expires_at=entity.expires_at,
        accepted_at=entity.accepted_at,
    )


def user_session_model_to_entity(model: UserSessionModel) -> UserSession:
    status = UserSessionStatus.revoked if model.revoked_at is not None else UserSessionStatus.active
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
