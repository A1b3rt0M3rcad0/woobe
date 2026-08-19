from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

from shared.contracts.unit_of_work import UnitOfWork


RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

Handler = Callable[[RequestT], Awaitable[ResponseT]]


class TransactionalHandler(Generic[RequestT, ResponseT]):
    def __init__(
        self,
        uow: UnitOfWork,
        handler: Handler[RequestT, ResponseT],
    ) -> None:
        self._uow = uow
        self._handler = handler

    async def __call__(self, request: RequestT) -> ResponseT:
        async with self._uow:
            return await self._handler(request)
