from typing import Generic, TypeVar, cast
from uuid import UUID

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.objects import CursorPage
from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.database.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseSQLAlchemyRepository(Generic[T]):

    def __init__(self, session: AsyncSession | UnitOfWork, model_cls: type[T]) -> None:
        self._session_or_uow: AsyncSession | UnitOfWork = session
        self.model_cls = model_cls

    @property
    def _session(self) -> AsyncSession:
        if isinstance(self._session_or_uow, UnitOfWork):
            return self._session_or_uow.session
        return cast(AsyncSession, self._session_or_uow)

    async def _add_model(self, model: T) -> T:
        self._session.add(model)
        return model

    async def _get_model_by_id(self, id: UUID) -> T | None:
        result = await self._session.get(self.model_cls, id)
        return result

    async def _delete_model(self, model: T) -> None:
        await self._session.delete(model)

    async def _flush(self) -> None:
        await self._session.flush()

    async def _refresh_model(self, model: T) -> None:
        await self._session.refresh(model)

    async def _paginate_models(
        self,
        statement: Select,
        *,
        limit: int = 50,
        cursor: str | None = None,
    ) -> CursorPage[T]:
        fetch_limit = limit + 1
        if cursor:
            try:
                cursor_uuid = UUID(cursor)
            except (ValueError, AttributeError):
                cursor_uuid = None
            if cursor_uuid is not None:
                statement = statement.where(self.model_cls.id < cursor_uuid)

        statement = statement.limit(fetch_limit)
        result = await self._session.execute(statement)
        rows = list(result.scalars().all())

        has_next = len(rows) > limit
        items = rows[:limit]
        next_cursor = str(items[-1].id) if items and has_next else None

        return CursorPage(
            items=items,
            cursor=cursor,
            next_cursor=next_cursor,
            has_next=has_next,
        )
