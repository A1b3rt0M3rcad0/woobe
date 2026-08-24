from sqlalchemy.ext.asyncio import AsyncEngine

from shared.infra.config import Settings
from shared.infra.database.session import create_engine


SETTINGS: Settings = Settings(service_role="api")
DATABASE_ENGINE: AsyncEngine = create_engine(SETTINGS)
