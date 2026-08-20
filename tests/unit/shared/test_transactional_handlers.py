from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Self

import pytest

from shared.infra.config.interface.unit_of_work import UnitOfWork
from shared.infra.streaming_transactional_handler import StreamingTransactionalHandler
from shared.infra.transactional_handler import TransactionalHandler


class RecordingUnitOfWork(UnitOfWork):
    def __init__(self) -> None:
        self.entered = 0
        self.exited = 0
        self.committed = False
        self.rolled_back = False

    @property
    def session(self) -> Any:
        raise RuntimeError("session is not used by this test double")

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def __aenter__(self) -> Self:
        self.entered += 1
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        self.exited += 1
        if exc_type is None:
            await self.commit()
        else:
            await self.rollback()


class StreamResponse:
    def __init__(self, stream: AsyncIterator[str]) -> None:
        self.stream = stream


async def _collect(stream: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in stream]


@pytest.mark.asyncio
async def test_transactional_handler_commits_after_success() -> None:
    uow = RecordingUnitOfWork()

    async def handler(value: int) -> int:
        return value + 1

    result = await TransactionalHandler(uow, handler)(1)

    assert result == 2
    assert uow.entered == 1
    assert uow.exited == 1
    assert uow.committed is True
    assert uow.rolled_back is False


@pytest.mark.asyncio
async def test_transactional_handler_rolls_back_after_failure() -> None:
    uow = RecordingUnitOfWork()

    async def handler(_: int) -> int:
        raise RuntimeError("failed")

    with pytest.raises(RuntimeError, match="failed"):
        await TransactionalHandler(uow, handler)(1)

    assert uow.entered == 1
    assert uow.exited == 1
    assert uow.committed is False
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_streaming_handler_rolls_back_if_handler_fails() -> None:
    uow = RecordingUnitOfWork()

    async def handler(_: int) -> StreamResponse:
        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        await StreamingTransactionalHandler(uow, handler)(1)

    assert uow.entered == 1
    assert uow.exited == 1
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_streaming_handler_commits_after_full_consumption() -> None:
    uow = RecordingUnitOfWork()

    async def source() -> AsyncIterator[str]:
        yield "first"
        yield "second"

    async def handler(_: int) -> StreamResponse:
        return StreamResponse(source())

    response = await StreamingTransactionalHandler(uow, handler)(1)

    assert uow.entered == 1
    assert uow.exited == 0
    assert await _collect(response.stream) == ["first", "second"]
    assert uow.exited == 1
    assert uow.committed is True
    assert uow.rolled_back is False


@pytest.mark.asyncio
async def test_streaming_handler_rolls_back_when_stream_fails() -> None:
    uow = RecordingUnitOfWork()

    async def source() -> AsyncIterator[str]:
        yield "partial"
        raise RuntimeError("stream failed")

    async def handler(_: int) -> StreamResponse:
        return StreamResponse(source())

    response = await StreamingTransactionalHandler(uow, handler)(1)

    with pytest.raises(RuntimeError, match="stream failed"):
        await _collect(response.stream)

    assert uow.exited == 1
    assert uow.committed is False
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_streaming_handler_rolls_back_when_consumer_closes_early() -> None:
    uow = RecordingUnitOfWork()

    async def source() -> AsyncIterator[str]:
        yield "first"
        yield "second"

    async def handler(_: int) -> StreamResponse:
        return StreamResponse(source())

    response = await StreamingTransactionalHandler(uow, handler)(1)
    stream = response.stream

    assert await anext(stream) == "first"
    await stream.aclose()

    assert uow.exited == 1
    assert uow.committed is False
    assert uow.rolled_back is True


@pytest.mark.asyncio
async def test_streaming_handler_can_close_uow_before_long_lived_stream() -> None:
    uow = RecordingUnitOfWork()

    async def source() -> AsyncIterator[str]:
        yield "event"

    async def handler(_: int) -> StreamResponse:
        return StreamResponse(source())

    response = await StreamingTransactionalHandler(
        uow,
        handler,
        keep_uow_open_for_stream=False,
    )(1)

    assert uow.entered == 1
    assert uow.exited == 1
    assert uow.committed is True
    assert await _collect(response.stream) == ["event"]
