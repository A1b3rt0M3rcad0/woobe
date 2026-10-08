from __future__ import annotations

from typing import Protocol, TypeVar

from shared.contracts.unit_of_work import UnitOfWork

RequestT = TypeVar("RequestT", contravariant=True)
ResponseT = TypeVar("ResponseT")


class TransactionReceipt(Protocol[RequestT, ResponseT]):
    """Record an effect using the owner's transaction, without moving its rules."""

    async def lookup(self, uow: UnitOfWork, request: RequestT) -> ResponseT | None: ...

    async def save(
        self, uow: UnitOfWork, request: RequestT, response: ResponseT
    ) -> None: ...
