from typing import Any

from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class TransactionalHandler:
    def __init__(self, uow: UnitOfWork, handler: Any) -> None:
        self._uow = uow
        self._handler = handler

    async def __call__(self, request: Request) -> Response:
        async with self._uow:
            return await self._handler(request)
