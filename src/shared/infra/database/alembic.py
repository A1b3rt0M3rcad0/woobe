from shared.infra.config import Settings

def get_alembic_config():
    settings = Settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2")
    return sync_url
