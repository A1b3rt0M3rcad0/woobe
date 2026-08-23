from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine

from modules.agent.infra.storage.factory import create_file_storage
from shared.infra.config import Settings
from shared.infra.database.session import create_engine


SETTINGS: Settings = Settings(service_role="api")
DATABASE_ENGINE: AsyncEngine = create_engine(SETTINGS)
FILE_STORAGE = create_file_storage(SETTINGS)
