from __future__ import annotations

import importlib
import logging
from uuid import UUID

from modules.agent.domain.ports.tool_repository import ToolRepository

logger = logging.getLogger(__name__)


class ToolsToolRepository(ToolRepository):

    def __init__(self, uow: object) -> None:
        self._uow = uow

    async def list_by_agent(self, agent_id: UUID, status: str | None = None) -> list:
        try:
            repos_mod = importlib.import_module("modules.tools.infra.database.repositories")
            repo = repos_mod.SQLAlchemyToolRepository(self._uow)
            return await repo.list_by_agent(agent_id, status=status)
        except Exception:
            logger.exception("Failed to list tools by agent")
            return []

    async def get_by_id(self, tool_id: UUID):
        try:
            repos_mod = importlib.import_module("modules.tools.infra.database.repositories")
            repo = repos_mod.SQLAlchemyToolRepository(self._uow)
            return await repo.get_by_id(tool_id)
        except Exception:
            logger.exception("Failed to get tool by id")
            return None
