from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from modules.network.infra.database.runtime_repositories import (
    NetworkRuntimeRepositories,
    build_network_runtime_repositories,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork

ResultT = TypeVar("ResultT")
UnitOfWorkFactory = Callable[[], NetworkUnitOfWork]
ReadOperation = Callable[[NetworkRuntimeRepositories], Awaitable[ResultT]]


class NetworkRuntimeTransactionRunner:
    """Execute short Network SQL read scopes without owning the long-lived stream."""

    def __init__(self, read_uow_factory: UnitOfWorkFactory) -> None:
        self._read_uow_factory = read_uow_factory

    async def read(self, operation: ReadOperation[ResultT]) -> ResultT:
        async with self._read_uow_factory() as uow:
            repositories = build_network_runtime_repositories(uow)
            return await operation(repositories)
