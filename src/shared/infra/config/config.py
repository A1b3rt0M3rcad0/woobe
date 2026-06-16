from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROJECTRAI_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/projectrai"
    debug: bool = False
    secret_key: str = Field(min_length=16)
    encryption_key: str = Field(min_length=16)
    db_pool_size: int = 20
    db_max_overflow: int = 10
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000"
    environment: str = "development"
    log_level: str = "INFO"
    host: str = "0.0.0.0"
    port: int = 8000
    worker_interval: float = 5.0
    rabbitmq_url: str = "amqp://projectrai:projectrai@localhost:5672/"
    rabbitmq_exchange: str = "domain.events"
    outbox_batch_size: int = 50
    inbox_batch_size: int = 50
    outbox_lock_timeout_seconds: int = 300
    inbox_lock_timeout_seconds: int = 300
    outbox_max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 300.0
    retry_backoff_multiplier: float = 2.0
