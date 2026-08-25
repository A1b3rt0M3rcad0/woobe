from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Generic, TypeVar

from shared.contracts.unit_of_work import UnitOfWork
from shared.infra.transactional_handler import Handler


RequestT = TypeVar("RequestT")
ResponseT = TypeVar("ResponseT")


class StreamingTransactionalHandler(Generic[RequestT, ResponseT]):
    def __init__(
        self,
        uow: UnitOfWork,
        handler: Handler[RequestT, ResponseT],
        *,
        keep_uow_open_for_stream: bool = True,
    ) -> None:
        self._uow = uow
        self._handler = handler
        self._keep_uow_open_for_stream = keep_uow_open_for_stream

    async def __call__(self, request: RequestT) -> ResponseT:
        await self._uow.__aenter__()
        try:
            response = await self._handler(request)
        except BaseException as error:
            await self._uow.__aexit__(
                type(error),
                error,
                error.__traceback__,
            )
            raise

        stream_attr, stream = self._find_stream(response)
        if stream_attr is None or stream is None or not self._keep_uow_open_for_stream:
            await self._uow.__aexit__(None, None, None)
            return response

        try:
            setattr(response, stream_attr, self._managed_stream(stream))
        except BaseException as error:
            await self._uow.__aexit__(
                type(error),
                error,
                error.__traceback__,
            )
            raise
        return response

    @staticmethod
    def _find_stream(response: ResponseT) -> tuple[str | None, Any | None]:
        for attribute in ("body_iterator", "stream"):
            stream = getattr(response, attribute, None)
            if stream is not None and hasattr(stream, "__aiter__"):
                return attribute, stream
        return None, None

    async def _managed_stream(self, source: Any) -> AsyncIterator[Any]:
        error: BaseException | None = None
        completed = False
        try:
            async for chunk in source:
                yield chunk
            completed = True
        except BaseException as caught:
            error = caught
            raise
        finally:
            if error is None and not completed:
                error = GeneratorExit()
            await self._uow.__aexit__(
                type(error) if error is not None else None,
                error,
                error.__traceback__ if error is not None else None,
            )
