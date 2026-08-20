from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from modules.agent.infra.database.database import AgentDatabase
from shared.infra.config import Settings
from shared.infra.database.session import create_engine, create_session_factory


SETTINGS: Settings = Settings(service_role="api")
DATABASE_ENGINE: AsyncEngine = create_engine(SETTINGS)
SESSION_FACTORY: async_sessionmaker[AsyncSession] = create_session_factory(DATABASE_ENGINE)
AGENT_DATABASE: AgentDatabase = AgentDatabase(SESSION_FACTORY)
