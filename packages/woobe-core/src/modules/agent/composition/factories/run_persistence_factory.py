from __future__ import annotations

from modules.agent.application.interfaces.run_persistence import AgentRunPersistencePort
from modules.agent.infra.execution.event_journal_run_persistence import (
    EventJournalAgentRunPersistence,
)
from modules.agent.infra.execution.legacy_run_persistence import LegacyAgentRunPersistence
from shared.infra.config import Settings


def build_agent_run_persistence(settings: Settings) -> AgentRunPersistencePort:
    if settings.run_persistence_mode == "legacy_finalization":
        return LegacyAgentRunPersistence()
    return EventJournalAgentRunPersistence()
