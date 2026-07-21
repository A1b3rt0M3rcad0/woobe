from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_INSECURE_SECRET_MARKERS = (
    "change-me",
    "changeme",
    "dev-secret",
    "dev-encryption",
    "donotuse",
    "password",
    "replace-with",
)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="PROJECTRAI_",
        env_file=".env",
        extra="ignore",
    )

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/projectrai"
    debug: bool = False
    secret_key: str = Field(min_length=32)
    encryption_key: str = Field(min_length=16)
    auth_issuer: str = "projectrai"
    auth_audience: str = "projectrai-web"
    access_token_ttl_seconds: int = Field(default=900, gt=0, le=3600)
    refresh_token_ttl_days: int = Field(default=30, gt=0, le=90)
    auth_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    access_cookie_name: str = "projectrai_access"
    access_cookie_secure: bool = False
    access_cookie_same_site: str = "lax"
    refresh_cookie_name: str = "projectrai_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_same_site: str = "lax"
    csrf_cookie_name: str = "projectrai_csrf"
    csrf_header_name: str = "x-csrf-token"
    login_rate_limit_attempts: int = Field(default=10, gt=0, le=100)
    login_rate_limit_window_seconds: int = Field(default=60, gt=0, le=3600)
    api_key_rate_limit_requests: int = Field(default=120, gt=0, le=10000)
    api_key_rate_limit_window_seconds: int = Field(default=60, gt=0, le=3600)
    runtime_max_concurrency_per_key: int = Field(default=4, gt=0, le=100)
    runtime_max_prompt_chars: int = Field(default=32768, gt=0, le=1048576)
    runtime_max_metadata_bytes: int = Field(default=16384, gt=0, le=1048576)
    runtime_max_snapshot_override_bytes: int = Field(default=32768, gt=0, le=4194304)
    runtime_max_request_bytes: int = Field(default=262144, gt=0, le=8388608)
    runtime_total_timeout_seconds: float = Field(default=120.0, gt=0, le=600)
    network_runtime_enabled: bool = True
    network_stream_heartbeat_seconds: float = Field(default=10.0, gt=0, le=60)
    network_max_depth_default: int = Field(default=4, ge=1, le=8)
    network_max_depth_hard: int = Field(default=8, ge=1, le=16)
    network_max_invocations_default: int = Field(default=16, ge=1, le=64)
    network_max_invocations_hard: int = Field(default=64, ge=1, le=128)
    network_timeout_default_seconds: int = Field(default=90, ge=1, le=300)
    network_timeout_hard_seconds: int = Field(default=300, ge=1, le=600)
    network_execution_lease_ttl_seconds: int = Field(default=30, ge=15, le=300)
    network_execution_lease_heartbeat_seconds: int = Field(default=10, ge=5, le=60)
    network_worker_prefetch: int = Field(default=4, ge=1, le=100)
    network_worker_slots: int = Field(default=4, ge=1, le=100)
    http_tool_timeout_max_ms: int = Field(default=30000, gt=0, le=120000)
    http_tool_response_max_bytes: int = Field(default=1048576, gt=0, le=16777216)
    db_pool_size: int = Field(default=20, gt=0, le=200)
    db_max_overflow: int = Field(default=10, ge=0, le=200)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:3000,http://127.0.0.1:3000"
    )
    trusted_hosts: str = "localhost,127.0.0.1,test"
    environment: str = "development"
    log_level: str = "INFO"
    json_logs: bool = False
    metrics_enabled: bool = True
    request_max_bytes: int = Field(default=1048576, gt=0, le=8388608)
    readiness_timeout_seconds: float = Field(default=3.0, gt=0, le=30)
    host: str = "0.0.0.0"
    port: int = 8000
    worker_interval: float = 5.0
    worker_health_file: str = "/tmp/projectrai/worker-health.json"
    worker_heartbeat_interval_seconds: float = Field(default=10.0, gt=0, le=60)
    worker_health_max_age_seconds: float = Field(default=45.0, gt=5, le=300)
    rabbitmq_url: str = "amqp://projectrai:projectrai@localhost:5672/"
    rabbitmq_exchange: str = "domain.events"
    redis_url: str | None = None
    redis_connect_timeout_seconds: float = Field(default=2.0, gt=0, le=30)
    storage_driver: str = "local"
    upload_max_mb: int = Field(default=25, gt=0, le=512)
    upload_allowed_extensions: str = ".txt,.md,.pdf,.docx"
    upload_local_dir: str = "./storage/uploads"
    rag_docx_max_uncompressed_mb: int = Field(default=100, gt=0, le=1024)
    rag_docx_max_entries: int = Field(default=1000, gt=0, le=10000)
    rag_docx_max_compression_ratio: float = Field(default=100.0, gt=1, le=10000)
    s3_bucket: str | None = None
    s3_region: str | None = None
    s3_prefix: str = "uploads"
    s3_endpoint_url: str | None = None
    s3_force_path_style: bool = False
    s3_server_side_encryption: str | None = "AES256"
    mcp_session_cache_enabled: bool = True
    mcp_session_key_prefix: str = "projectrai:mcp-session"
    mcp_session_ttl_seconds: int = Field(default=3600, gt=0, le=86400)
    outbox_batch_size: int = 50
    inbox_batch_size: int = 50
    outbox_lock_timeout_seconds: int = 300
    inbox_lock_timeout_seconds: int = 300
    outbox_max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 300.0
    retry_backoff_multiplier: float = 2.0

    @staticmethod
    def _is_weak_secret(value: str) -> bool:
        normalized = value.strip().lower()
        return (
            len(value.strip()) < 32
            or len(set(value)) < 12
            or any(marker in normalized for marker in _INSECURE_SECRET_MARKERS)
        )

    @staticmethod
    def _uses_default_credentials(url: str) -> bool:
        parsed = urlsplit(url.replace("postgresql+asyncpg://", "postgresql://", 1))
        username = (parsed.username or "").lower()
        password = (parsed.password or "").lower()
        return (username, password) in {
            ("postgres", "postgres"),
            ("projectrai", "projectrai"),
            ("guest", "guest"),
        }

    @model_validator(mode="after")
    def validate_network_runtime(self) -> Settings:
        errors: list[str] = []
        if self.network_max_depth_default > self.network_max_depth_hard:
            errors.append("Network default max depth exceeds hard max depth")
        if self.network_max_invocations_default > self.network_max_invocations_hard:
            errors.append("Network default max invocations exceeds hard max invocations")
        if self.network_timeout_default_seconds > self.network_timeout_hard_seconds:
            errors.append("Network default timeout exceeds hard timeout")
        if (
            self.network_execution_lease_heartbeat_seconds * 2
            >= self.network_execution_lease_ttl_seconds
        ):
            errors.append("Network lease TTL must exceed two heartbeat intervals")
        if errors:
            raise ValueError("; ".join(errors))
        return self

    @model_validator(mode="after")
    def validate_runtime_security(self) -> Settings:
        environment = self.environment.strip().lower()
        if environment not in {"production", "prod"}:
            return self

        errors: list[str] = []
        if self.debug:
            errors.append("PROJECTRAI_DEBUG must be false in production")
        if self._is_weak_secret(self.secret_key):
            errors.append("PROJECTRAI_SECRET_KEY is weak or uses a known placeholder")
        if self._is_weak_secret(self.encryption_key):
            errors.append("PROJECTRAI_ENCRYPTION_KEY is weak or uses a known placeholder")
        if not self.access_cookie_secure:
            errors.append("PROJECTRAI_ACCESS_COOKIE_SECURE must be true in production")
        if not self.refresh_cookie_secure:
            errors.append("PROJECTRAI_REFRESH_COOKIE_SECURE must be true in production")

        origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
        if not origins or "*" in origins:
            errors.append("PROJECTRAI_CORS_ORIGINS must contain exact origins")
        if any(origin.startswith("http://") for origin in origins):
            errors.append("PROJECTRAI_CORS_ORIGINS must use HTTPS in production")

        trusted_hosts = [item.strip() for item in self.trusted_hosts.split(",") if item.strip()]
        if not trusted_hosts or "*" in trusted_hosts:
            errors.append("PROJECTRAI_TRUSTED_HOSTS must contain exact hostnames")

        if self._uses_default_credentials(self.database_url):
            errors.append("PROJECTRAI_DATABASE_URL uses default credentials")
        if self._uses_default_credentials(self.rabbitmq_url):
            errors.append("PROJECTRAI_RABBITMQ_URL uses default credentials")
        if not self.json_logs:
            errors.append("PROJECTRAI_JSON_LOGS must be true in production")

        if errors:
            raise ValueError("; ".join(errors))
        return self
