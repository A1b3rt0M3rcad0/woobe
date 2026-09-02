from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func, or_, select

from modules.agent.domain.entities import Session
from modules.agent.domain.errors import SessionNotFoundError
from modules.agent.infra.database.mappers import model_to_session, session_to_model
from modules.agent.infra.database.models import MessageModel, SessionModel
from modules.agent.infra.database.repositories import SQLAlchemySessionRepository
from shared.contracts.errors import ValidationError
from shared.contracts.pagination import CursorPage


class SQLAlchemyRuntimeSessionRepository(SQLAlchemySessionRepository):
    """Session persistence with environment provenance as first-class fields."""

    @staticmethod
    def _to_entity(model: SessionModel) -> Session:
        entity = model_to_session(model)
        entity.runtime_environment = model.runtime_environment
        entity.opened_release_id = model.opened_release_id
        return entity

    @staticmethod
    def _to_model(entity: Session) -> SessionModel:
        model = session_to_model(entity)
        model.runtime_environment = entity.runtime_environment
        model.opened_release_id = entity.opened_release_id
        return model

    async def create(self, session: Session) -> Session:
        model = self._to_model(session)
        await self._base._add_model(model)
        await self._base._flush()
        await self._base._refresh_model(model)
        return self._to_entity(model)

    async def get_by_id(self, session_id: UUID) -> Session:
        model = await self._base._get_model_by_id(session_id)
        if model is None:
            raise SessionNotFoundError(session_id)
        return self._to_entity(model)

    async def is_chat_surface_bound(
        self,
        *,
        session_id: UUID,
        project_id: UUID,
        agent_id: UUID,
        agent_release_id: UUID,
        chat_surface_id: UUID,
    ) -> bool:
        statement = select(SessionModel.id).where(
            SessionModel.id == session_id,
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
            SessionModel.runtime_environment == "production",
            SessionModel.opened_release_id == agent_release_id,
            SessionModel.chat_surface_id == chat_surface_id,
            SessionModel.origin == "chat_surface",
            SessionModel.status == "active",
        )
        return await self._session.scalar(statement) is not None

    async def get_by_external_id(
        self,
        project_id: UUID,
        agent_id: UUID,
        external_session_id: str,
    ) -> Session:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
            SessionModel.external_session_id == external_session_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model is None:
            raise SessionNotFoundError(session_id=external_session_id)
        return self._to_entity(model)

    async def list_by_agent(
        self,
        project_id: UUID,
        agent_id: UUID,
        status: str | None = None,
    ) -> list[Session]:
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
        )
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(
            func.coalesce(SessionModel.last_message_at, SessionModel.created_at).desc(),
            SessionModel.id.desc(),
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def list_by_project(
        self,
        project_id: UUID,
        status: str | None = None,
    ) -> list[Session]:
        stmt = select(SessionModel).where(SessionModel.project_id == project_id)
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.created_at.desc(), SessionModel.id.desc())
        result = await self._session.execute(stmt)
        return [self._to_entity(model) for model in result.scalars().all()]

    async def paginate_by_project(
        self,
        project_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> CursorPage[Session]:
        stmt = select(SessionModel).where(SessionModel.project_id == project_id)
        if status:
            stmt = stmt.where(SessionModel.status == status)
        stmt = stmt.order_by(SessionModel.id.desc())
        page = await self._base._paginate_models(stmt, limit=limit, cursor=cursor)
        return CursorPage(
            items=[self._to_entity(model) for model in page.items],
            cursor=page.cursor,
            next_cursor=page.next_cursor,
            has_next=page.has_next,
            total=page.total,
        )

    async def paginate_by_agent_environment(
        self,
        project_id: UUID,
        agent_id: UUID,
        environment: str,
        *,
        limit: int = 20,
        cursor: str | None = None,
    ) -> CursorPage[tuple[Session, int]]:
        activity = func.coalesce(SessionModel.last_message_at, SessionModel.created_at)
        stmt = select(SessionModel).where(
            SessionModel.project_id == project_id,
            SessionModel.agent_id == agent_id,
            SessionModel.runtime_environment == environment,
        )

        if cursor:
            try:
                cursor_id = UUID(cursor)
            except (TypeError, ValueError) as exc:
                raise ValidationError("Invalid Agent Session cursor") from exc

            cursor_result = await self._session.execute(
                select(SessionModel).where(
                    SessionModel.id == cursor_id,
                    SessionModel.project_id == project_id,
                    SessionModel.agent_id == agent_id,
                    SessionModel.runtime_environment == environment,
                )
            )
            cursor_model = cursor_result.scalar_one_or_none()
            if cursor_model is None:
                raise ValidationError("Agent Session cursor was not found in this environment")

            cursor_activity = cursor_model.last_message_at or cursor_model.created_at
            if cursor_activity is not None:
                stmt = stmt.where(
                    or_(
                        activity < cursor_activity,
                        and_(activity == cursor_activity, SessionModel.id < cursor_id),
                    )
                )
            else:
                stmt = stmt.where(SessionModel.id < cursor_id)

        stmt = stmt.order_by(activity.desc(), SessionModel.id.desc()).limit(limit + 1)
        result = await self._session.execute(stmt)
        models = list(result.scalars().all())
        has_next = len(models) > limit
        visible_models = models[:limit]

        counts: dict[UUID, int] = {}
        visible_ids = [model.id for model in visible_models]
        if visible_ids:
            count_result = await self._session.execute(
                select(MessageModel.session_id, func.count(MessageModel.id))
                .where(MessageModel.session_id.in_(visible_ids))
                .group_by(MessageModel.session_id)
            )
            counts = {session_id: int(count) for session_id, count in count_result.all()}

        items = [
            (self._to_entity(model), counts.get(model.id, 0))
            for model in visible_models
        ]
        next_cursor = str(visible_models[-1].id) if has_next and visible_models else None
        return CursorPage(
            items=items,
            cursor=cursor,
            next_cursor=next_cursor,
            has_next=has_next,
            total=None,
        )

    async def update(self, session: Session) -> Session:
        model = await self._base._get_model_by_id(session.id)
        if model is None:
            raise SessionNotFoundError(session.id)
        model.runtime_environment = session.runtime_environment
        model.opened_release_id = session.opened_release_id
        model.external_session_id = session.external_session_id
        model.tenant_id = session.tenant_id
        model.user_id = session.user_id
        model.status = session.status.value if hasattr(session.status, "value") else session.status
        model.mode = session.mode.value if hasattr(session.mode, "value") else session.mode
        model.data = session.data
        model.last_message_at = session.last_message_at
        await self._base._flush()
        return self._to_entity(model)
