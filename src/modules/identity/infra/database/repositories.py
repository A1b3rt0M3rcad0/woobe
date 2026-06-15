from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.identity.domain.entities import (
    Organization,
    OrganizationInvite,
    OrganizationMember,
    User,
    UserSession,
)
from modules.identity.domain.repositories import (
    OrganizationInviteRepository as OrganizationInviteRepositoryInterface,
    OrganizationMemberRepository as OrganizationMemberRepositoryInterface,
    OrganizationRepository as OrganizationRepositoryInterface,
    UserRepository as UserRepositoryInterface,
    UserSessionRepository as UserSessionRepositoryInterface,
)
from modules.identity.infra.database.mappers import (
    organization_invite_entity_to_model,
    organization_invite_model_to_entity,
    organization_member_entity_to_model,
    organization_member_model_to_entity,
    organization_entity_to_model,
    organization_model_to_entity,
    user_entity_to_model,
    user_model_to_entity,
    user_session_entity_to_model,
    user_session_model_to_entity,
)
from modules.identity.infra.database.models import (
    OrganizationInviteModel,
    OrganizationMemberModel,
    OrganizationModel,
    OutboxEventModel,
    UserModel,
    UserSessionModel,
)
from shared.messaging.outbox_writer import OutboxEventWriter
from shared.infra.objects import CursorPage
from shared.infra.repositories.base_repository import BaseSQLAlchemyRepository


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
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return user_model_to_entity(model) if model else None

    async def delete(self, user_id: UUID) -> None:
        model = await self._get_model_by_id(user_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOrganizationRepository(
    BaseSQLAlchemyRepository[OrganizationModel], OrganizationRepositoryInterface
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, OrganizationModel)

    async def save(self, organization: Organization) -> Organization:
        model = organization_entity_to_model(organization)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return organization_model_to_entity(model)

    async def get_by_id(self, organization_id: UUID) -> Organization | None:
        model = await self._get_model_by_id(organization_id)
        return organization_model_to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Organization | None:
        result = await self._session.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return organization_model_to_entity(model) if model else None

    async def list_all(self) -> list[Organization]:
        from sqlalchemy import select as sa_select
        stmt = sa_select(OrganizationModel).order_by(OrganizationModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [organization_model_to_entity(o) for o in result.scalars().all()]

    async def delete(self, organization_id: UUID) -> None:
        model = await self._get_model_by_id(organization_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOrganizationMemberRepository(
    BaseSQLAlchemyRepository[OrganizationMemberModel],
    OrganizationMemberRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, OrganizationMemberModel)

    async def save(self, member: OrganizationMember) -> OrganizationMember:
        model = organization_member_entity_to_model(member)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return organization_member_model_to_entity(model)

    async def get_by_id(self, member_id: UUID) -> OrganizationMember | None:
        model = await self._get_model_by_id(member_id)
        return organization_member_model_to_entity(model) if model else None

    async def get_by_organization_and_user(
        self, organization_id: UUID, user_id: UUID
    ) -> OrganizationMember | None:
        result = await self._session.execute(
            select(OrganizationMemberModel).where(
                OrganizationMemberModel.organization_id == organization_id,
                OrganizationMemberModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        return organization_member_model_to_entity(model) if model else None

    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[OrganizationMember]:
        result = await self._session.execute(
            select(OrganizationMemberModel).where(
                OrganizationMemberModel.organization_id == organization_id
            )
        )
        return [organization_member_model_to_entity(m) for m in result.scalars().all()]

    async def list_by_user(self, user_id: UUID) -> list[OrganizationMember]:
        result = await self._session.execute(
            select(OrganizationMemberModel).where(
                OrganizationMemberModel.user_id == user_id
            )
        )
        return [organization_member_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_organization(
        self, organization_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationMember]:
        stmt = (
            select(OrganizationMemberModel)
            .where(OrganizationMemberModel.organization_id == organization_id)
            .order_by(OrganizationMemberModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[organization_member_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationMember]:
        stmt = (
            select(OrganizationMemberModel)
            .where(OrganizationMemberModel.user_id == user_id)
            .order_by(OrganizationMemberModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[organization_member_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, member_id: UUID) -> None:
        model = await self._get_model_by_id(member_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyOrganizationInviteRepository(
    BaseSQLAlchemyRepository[OrganizationInviteModel],
    OrganizationInviteRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, OrganizationInviteModel)

    async def save(self, invite: OrganizationInvite) -> OrganizationInvite:
        model = organization_invite_entity_to_model(invite)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return organization_invite_model_to_entity(model)

    async def get_by_id(self, invite_id: UUID) -> OrganizationInvite | None:
        model = await self._get_model_by_id(invite_id)
        return organization_invite_model_to_entity(model) if model else None

    async def get_by_organization_and_email(
        self, organization_id: UUID, email: str
    ) -> OrganizationInvite | None:
        result = await self._session.execute(
            select(OrganizationInviteModel).where(
                OrganizationInviteModel.organization_id == organization_id,
                OrganizationInviteModel.email == email,
            )
        )
        model = result.scalar_one_or_none()
        return organization_invite_model_to_entity(model) if model else None

    async def list_by_organization(
        self, organization_id: UUID
    ) -> list[OrganizationInvite]:
        result = await self._session.execute(
            select(OrganizationInviteModel).where(
                OrganizationInviteModel.organization_id == organization_id
            )
        )
        return [
            organization_invite_model_to_entity(i) for i in result.scalars().all()
        ]

    async def paginate_by_organization(
        self, organization_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[OrganizationInvite]:
        stmt = (
            select(OrganizationInviteModel)
            .where(OrganizationInviteModel.organization_id == organization_id)
            .order_by(OrganizationInviteModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[organization_invite_model_to_entity(i) for i in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

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
        return [user_session_model_to_entity(s) for s in result.scalars().all()]

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
            items=[user_session_model_to_entity(s) for s in page.items],
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
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload=payload,
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self._session.add(event)
