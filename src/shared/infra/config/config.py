from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="PROJECTRAI_", env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/projectrai"
    debug: bool = False
    secret_key: str = Field(min_length=32)
    encryption_key: str = Field(min_length=16)
    auth_issuer: str = "projectrai"
    auth_audience: str = "projectrai-web"
    access_token_ttl_seconds: int = Field(default=900, gt=0, le=3600)
    refresh_token_ttl_days: int = Field(default=30, gt=0, le=90)
    auth_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    refresh_cookie_name: str = "projectrai_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_same_site: str = "lax"
    login_rate_limit_attempts: int = Field(default=10, gt=0, le=100)
    login_rate_limit_window_seconds: int = Field(default=60, gt=0, le=3600)
    api_key_rate_limit_requests: int = Field(default=120, gt=0, le=10000)
    api_key_rate_limit_window_seconds: int = Field(default=60, gt=0, le=3600)
    runtime_max_concurrency_per_key: int = Field(default=4, gt=0, le=100)
    runtime_max_prompt_chars: int = Field(default=32768, gt=0, le=1048576)
    runtime_max_metadata_bytes: int = Field(default=16384, gt=0, le=1048576)
    runtime_max_snapshot_override_bytes: int = Field(default=65536, gt=0, le=4194304)
    runtime_max_request_bytes: int = Field(default=262144, gt=0, le=8388608)
    runtime_total_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    http_tool_timeout_max_ms: int = Field(default=30000, gt=0, le=120000)
    http_tool_response_max_bytes: int = Field(default=1048576, gt=0, le=16777216)
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
