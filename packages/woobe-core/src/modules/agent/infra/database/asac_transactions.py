"""ASaC short scopes use the Agent's existing transaction owner."""
from contextlib import asynccontextmanager


class AgentASaCTransactions:
    def __init__(self, uow_factory):
        self.uow_factory = uow_factory

    @asynccontextmanager
    async def read(self):
        uow = self.uow_factory()
        uow.mark_read_only()
        async with uow:
            yield uow.session

    @asynccontextmanager
    async def begin(self):
        uow = self.uow_factory()
        async with uow:
            yield uow.session
