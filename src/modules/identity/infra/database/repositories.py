from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.config.interface.unit_of_work import UnitOfWork

from modules.identity.domain.entities import (
    Workspace,
    WorkspaceInvite,
    WorkspaceMember,
    User,
    UserSession,
)
from modules.identity.domain.repositories import (
    WorkspaceInviteRepository as WorkspaceInviteRepositoryInterface,
    WorkspaceMemberRepository as WorkspaceMemberRepositoryInterface,
    WorkspaceRepository as WorkspaceRepositoryInterface,
    UserRepository as UserRepositoryInterface,
    UserSessionRepository as UserSessionRepositoryInterface,
)
from modules.identity.infra.database.mappers import (
    workspace_invite_entity_to_model,
    workspace_invite_model_to_entity,
    workspace_member_entity_to_model,
    workspace_member_model_to_entity,
    workspace_entity_to_model,
    workspace_model_to_entity,
    user_entity_to_model,
    user_model_to_entity,
    user_session_entity_to_model,
    user_session_model_to_entity,
)
from modules.identity.infra.database.models import (
    WorkspaceInviteModel,
    WorkspaceMemberModel,
    WorkspaceModel,
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


class SQLAlchemyWorkspaceRepository(
    BaseSQLAlchemyRepository[WorkspaceModel], WorkspaceRepositoryInterface
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, WorkspaceModel)

    async def save(self, workspace: Workspace) -> Workspace:
        model = workspace_entity_to_model(workspace)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return workspace_model_to_entity(model)

    async def get_by_id(self, workspace_id: UUID) -> Workspace | None:
        model = await self._get_model_by_id(workspace_id)
        return workspace_model_to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Workspace | None:
        result = await self._session.execute(
            select(WorkspaceModel).where(WorkspaceModel.slug == slug)
        )
        model = result.scalar_one_or_none()
        return workspace_model_to_entity(model) if model else None

    async def list_all(self) -> list[Workspace]:
        from sqlalchemy import select as sa_select
        stmt = sa_select(WorkspaceModel).order_by(WorkspaceModel.created_at.desc())
        result = await self._session.execute(stmt)
        return [workspace_model_to_entity(workspace) for workspace in result.scalars().all()]

    async def delete(self, workspace_id: UUID) -> None:
        model = await self._get_model_by_id(workspace_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyWorkspaceMemberRepository(
    BaseSQLAlchemyRepository[WorkspaceMemberModel],
    WorkspaceMemberRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, WorkspaceMemberModel)

    async def save(self, member: WorkspaceMember) -> WorkspaceMember:
        model = workspace_member_entity_to_model(member)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return workspace_member_model_to_entity(model)

    async def get_by_id(self, member_id: UUID) -> WorkspaceMember | None:
        model = await self._get_model_by_id(member_id)
        return workspace_member_model_to_entity(model) if model else None

    async def get_by_workspace_and_user(
        self, workspace_id: UUID, user_id: UUID
    ) -> WorkspaceMember | None:
        result = await self._session.execute(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.workspace_id == workspace_id,
                WorkspaceMemberModel.user_id == user_id,
            )
        )
        model = result.scalar_one_or_none()
        return workspace_member_model_to_entity(model) if model else None

    async def list_by_workspace(
        self, workspace_id: UUID
    ) -> list[WorkspaceMember]:
        result = await self._session.execute(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.workspace_id == workspace_id
            )
        )
        return [workspace_member_model_to_entity(m) for m in result.scalars().all()]

    async def list_by_user(self, user_id: UUID) -> list[WorkspaceMember]:
        result = await self._session.execute(
            select(WorkspaceMemberModel).where(
                WorkspaceMemberModel.user_id == user_id
            )
        )
        return [workspace_member_model_to_entity(m) for m in result.scalars().all()]

    async def paginate_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceMember]:
        stmt = (
            select(WorkspaceMemberModel)
            .where(WorkspaceMemberModel.workspace_id == workspace_id)
            .order_by(WorkspaceMemberModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[workspace_member_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_user(
        self, user_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceMember]:
        stmt = (
            select(WorkspaceMemberModel)
            .where(WorkspaceMemberModel.user_id == user_id)
            .order_by(WorkspaceMemberModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[workspace_member_model_to_entity(m) for m in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def delete(self, member_id: UUID) -> None:
        model = await self._get_model_by_id(member_id)
        if model:
            await self._delete_model(model)


class SQLAlchemyWorkspaceInviteRepository(
    BaseSQLAlchemyRepository[WorkspaceInviteModel],
    WorkspaceInviteRepositoryInterface,
):

    def __init__(self, session: AsyncSession | UnitOfWork) -> None:
        super().__init__(session, WorkspaceInviteModel)

    async def save(self, invite: WorkspaceInvite) -> WorkspaceInvite:
        model = workspace_invite_entity_to_model(invite)
        await self._add_model(model)
        await self._flush()
        await self._refresh_model(model)
        return workspace_invite_model_to_entity(model)

    async def get_by_id(self, invite_id: UUID) -> WorkspaceInvite | None:
        model = await self._get_model_by_id(invite_id)
        return workspace_invite_model_to_entity(model) if model else None

    async def get_by_workspace_and_email(
        self, workspace_id: UUID, email: str
    ) -> WorkspaceInvite | None:
        result = await self._session.execute(
            select(WorkspaceInviteModel).where(
                WorkspaceInviteModel.workspace_id == workspace_id,
                WorkspaceInviteModel.email == email,
            )
        )
        model = result.scalar_one_or_none()
        return workspace_invite_model_to_entity(model) if model else None

    async def list_by_workspace(
        self, workspace_id: UUID
    ) -> list[WorkspaceInvite]:
        result = await self._session.execute(
            select(WorkspaceInviteModel).where(
                WorkspaceInviteModel.workspace_id == workspace_id
            )
        )
        return [
            workspace_invite_model_to_entity(i) for i in result.scalars().all()
        ]

    async def paginate_by_workspace(
        self, workspace_id: UUID, *, limit: int = 50, cursor: str | None = None
    ) -> CursorPage[WorkspaceInvite]:
        stmt = (
            select(WorkspaceInviteModel)
            .where(WorkspaceInviteModel.workspace_id == workspace_id)
            .order_by(WorkspaceInviteModel.id.desc())
        )
        page = await self._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[workspace_invite_model_to_entity(i) for i in page.items],
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
        routing_key: str,
        idempotency_key: str,
        event_version: int = 1,
        correlation_id: UUID | None = None,
        causation_id: UUID | None = None,
    ) -> None:
        event = OutboxEventModel(
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
        self._session.add(event)
