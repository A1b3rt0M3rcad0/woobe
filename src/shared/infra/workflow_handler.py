from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar


RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")

Handler = Callable[[RequestT], Awaitable[ResponseT]]


class WorkflowHandler(Generic[RequestT, ResponseT]):
    """Marker wrapper for long-lived workflows without a global DB transaction.

    Persistence phases inside the workflow must cross explicit transactional
    boundaries of their own. This wrapper deliberately does not own a UnitOfWork.
    """

    def __init__(self, handler: Handler[RequestT, ResponseT]) -> None:
        self._handler = handler

    async def __call__(self, request: RequestT) -> ResponseT:
        return await self._handler(request)
