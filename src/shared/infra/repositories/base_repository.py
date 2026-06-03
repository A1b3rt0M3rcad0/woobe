from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.database.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):

    def __init__(self, session: AsyncSession, model_cls: type[T]) -> None:
        self.session = session
        self.model_cls = model_cls

    async def add(self, model: T) -> T:
        self.session.add(model)
        return model

    async def get_by_id(self, id: UUID) -> T | None:
        result = await self.session.get(self.model_cls, id)
        return result

    async def list_all(self) -> list[T]:
        result = await self.session.execute(select(self.model_cls))
        return list(result.scalars().all())

    async def delete(self, model: T) -> None:
        await self.session.delete(model)
