from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from uuid import UUID

import uuid6

from modules.identity.infra.database.models import UserSessionModel
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from shared.infra.errors import AuthenticationError
from shared.security.refresh_tokens import generate_refresh_token, hash_refresh_token


@dataclass(frozen=True)
class IssuedSession:
    id: UUID
    user_id: UUID
    secret: str


class SessionLifecycle:
    def __init__(self, *, ttl_days: int) -> None:
        self._ttl_days = ttl_days

    async def issue(
        self,
        uow: IdentityUnitOfWork,
        *,
        user_id: UUID,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedSession:
        now = datetime.now(UTC)
        session_id = uuid6.uuid7()
        secret = generate_refresh_token()
        model = UserSessionModel(
            id=session_id,
            user_id=user_id,
            refresh_token_hash=hash_refresh_token(secret),
            user_agent=user_agent,
            ip_address=ip_address,
            expires_at=now + timedelta(days=self._ttl_days),
            last_used_at=now,
        )
        uow.session.add(model)
        await uow.session.flush()
        return IssuedSession(id=session_id, user_id=user_id, secret=secret)

    async def rotate(
        self,
        uow: IdentityUnitOfWork,
        *,
        session_id: UUID,
        secret: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> IssuedSession:
        now = datetime.now(UTC)
        model = await uow.session.get(UserSessionModel, session_id, with_for_update=True)
        if model is None or not compare_digest(
            model.refresh_token_hash,
            hash_refresh_token(secret),
        ):
            raise AuthenticationError("Invalid refresh session")

        if model.revoked_at is not None or model.replaced_by_session_id is not None:
            await self.revoke_all(uow, model.user_id)
            await uow.commit()
            raise AuthenticationError("Refresh session reuse detected")
        if self._as_utc(model.expires_at) <= now:
            model.revoked_at = now
            model.updated_at = now
            await uow.commit()
            raise AuthenticationError("Refresh session expired")

        replacement = await self.issue(
            uow,
            user_id=model.user_id,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        model.replaced_by_session_id = replacement.id
        model.last_used_at = now
        model.updated_at = now
        return replacement

    async def revoke(
        self,
        uow: IdentityUnitOfWork,
        *,
        session_id: UUID | None,
        secret: str | None,
    ) -> None:
        if session_id is None or secret is None:
            return
        model = await uow.session.get(UserSessionModel, session_id, with_for_update=True)
        if model is None or not compare_digest(
            model.refresh_token_hash,
            hash_refresh_token(secret),
        ):
            return
        now = datetime.now(UTC)
        model.revoked_at = model.revoked_at or now
        model.updated_at = now

    async def revoke_all(self, uow: IdentityUnitOfWork, user_id: UUID) -> None:
        now = datetime.now(UTC)
        sessions = await uow.user_sessions.list_by_user(user_id)
        for session in sessions:
            model = await uow.session.get(UserSessionModel, session.id)
            if model is not None and model.revoked_at is None:
                model.revoked_at = now
                model.updated_at = now

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)
