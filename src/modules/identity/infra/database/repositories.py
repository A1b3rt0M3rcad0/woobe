from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from modules.identity.domain.entities import User, UserInvite, UserSession
from modules.identity.domain.repositories import (
    UserInviteRepository as UserInviteRepositoryInterface,
    UserRepository as UserRepositoryInterface,
    UserSessionRepository as UserSessionRepositoryInterface,
)
from modules.identity.infra.database.mappers import (
    user_entity_to_model,
    user_invite_entity_to_model,
    user_invite_model_to_entity,
    user_model_to_entity,
    user_session_entity_to_model,
    user_session_model_to_entity,
)
from modules.identity.infra.database.models import (
    OutboxEventModel,
    UserInviteModel,
    UserModel,
    UserSessionModel,
)
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository
from shared.messaging.outbox_writer import OutboxEventWriter


class SQLAlchemyUserRepository(BaseSQLAlchemyRepository[UserModel], UserRepositoryInterface):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, UserModel)

    async def save(self, user: User) -> User:
        model = user_entity_to_model(user)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return user_model_to_entity(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._get_model_by_id(user_id)
        return user_model_to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(select(UserModel).where(UserModel.email == email))
        model = result.scalar_one_or_none()
        return user_model_to_entity(model) if model else None

    async def delete(self, user_id: UUID) -> None:
        model = await self._get_model_by_id(user_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyUserInviteRepository(
    BaseSQLAlchemyRepository[UserInviteModel], UserInviteRepositoryInterface
):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, UserInviteModel)

    async def save(self, invite: UserInvite) -> UserInvite:
        model = user_invite_entity_to_model(invite)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return user_invite_model_to_entity(model)

    async def get_by_id(self, invite_id: UUID) -> UserInvite | None:
        model = await self._get_model_by_id(invite_id)
        return user_invite_model_to_entity(model) if model else None

    async def get_by_workspace_and_email(
        self, workspace_id: UUID, email: str
    ) -> UserInvite | None:
        result = await self._session.execute(
            select(UserInviteModel).where(
                UserInviteModel.workspace_id == workspace_id,
                UserInviteModel.email == email,
            )
        )
        model = result.scalar_one_or_none()
        return user_invite_model_to_entity(model) if model else None

    async def list_by_workspace(self, workspace_id: UUID) -> list[UserInvite]:
        result = await self._session.execute(
            select(UserInviteModel).where(UserInviteModel.workspace_id == workspace_id)
        )
        return [user_invite_model_to_entity(item) for item in result.scalars().all()]

    async def delete(self, invite_id: UUID) -> None:
        model = await self._get_model_by_id(invite_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyUserSessionRepository(
    BaseSQLAlchemyRepository[UserSessionModel], UserSessionRepositoryInterface
):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, UserSessionModel)

    async def save(self, session: UserSession) -> UserSession:
        model = user_session_entity_to_model(session)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return user_session_model_to_entity(model)

    async def get_by_id(self, session_id: UUID) -> UserSession | None:
        model = await self._get_model_by_id(session_id)
        return user_session_model_to_entity(model) if model else None

    async def list_by_user(self, user_id: UUID) -> list[UserSession]:
        result = await self._session.execute(
            select(UserSessionModel).where(UserSessionModel.user_id == user_id)
        )
        return [user_session_model_to_entity(item) for item in result.scalars().all()]

    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[UserSession]:
        stmt = (
            select(UserSessionModel)
            .where(UserSessionModel.user_id == user_id)
            .order_by(UserSessionModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[user_session_model_to_entity(item) for item in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, session_id: UUID) -> None:
        model = await self._get_model_by_id(session_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOutboxEventWriter(OutboxEventWriter):
    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return self._session_or_uow

    async def write(
        self,
        aggregate_type: str,
        aggregate_id: UUID,
        event_type: str,
        payload: dict[str, Any],
        routing_key: str,
        idempotency_key: str,
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        self._session.add(
            OutboxEventModel(
                aggregate_type=aggregate_type,
                aggregate_id=aggregate_id,
                event_type=event_type,
                event_version=event_version,
                routing_key=routing_key,
                payload=payload,
                idempotency_key=idempotency_key,
                correlation_id=correlation_id,
                causation_id=causation_id,
            )
        )
