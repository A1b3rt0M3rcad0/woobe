"""ASaC short scopes use the Agent's existing transaction owner."""
from contextlib import asynccontextmanager
from shared.infra.asac_draft_store import ASaCDraftStore


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


class AgentASaCDraftStore(ASaCDraftStore):
    """Owner adapter wires the shared persistence mechanism to Agent tables/UoW."""
    def __init__(self, *, uow_factory, owner, artifacts, cursor_key=None):
        from modules.agent.infra.database.asac_models import (
            ASaCDraftModel, ASaCRevisionModel, ASaCOperationModel, ASaCResourceModel,
        )
        super().__init__(transactions=AgentASaCTransactions(uow_factory),
            kind="Agent", owner=owner, drafts=ASaCDraftModel,
            revisions=ASaCRevisionModel, operations=ASaCOperationModel,
            identities=ASaCResourceModel, artifacts=artifacts, cursor_key=cursor_key)


from shared.infra.asac_candidate_store import ASaCCandidateStore

class AgentASaCCandidateStore(ASaCCandidateStore):
    """Agent-owned adapter for candidate receipt mechanics."""
