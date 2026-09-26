from __future__ import annotations

from urllib.parse import urlsplit

from pydantic import Field, field_validator, model_validator
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


def _normalize_async_postgres_url(value: str) -> str:
    normalized = value.strip()
    if normalized.startswith("postgres://"):
        return normalized.replace("postgres://", "postgresql+asyncpg://", 1)
    if normalized.startswith("postgresql://"):
        return normalized.replace("postgresql://", "postgresql+asyncpg://", 1)
    return normalized


def _validate_connection_url(value: str, *, schemes: set[str], variable: str) -> str:
    normalized = value.strip()
    if not normalized:
        return normalized
    parseable = normalized.replace("postgresql+asyncpg://", "postgresql://", 1)
    parsed = urlsplit(parseable)
    if parsed.scheme not in schemes or not parsed.hostname:
        expected = ", ".join(sorted(schemes))
        raise ValueError(f"{variable} must use one of [{expected}] and include a hostname")
    return normalized


def _validate_database_url(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        return normalized
    parsed = urlsplit(normalized.replace("postgresql+asyncpg://", "postgresql://", 1))
    if parsed.scheme == "postgresql":
        if not parsed.hostname:
            raise ValueError("WOOBE_DATABASE_URL must include a PostgreSQL hostname")
        return normalized
    if parsed.scheme in {"sqlite", "sqlite+aiosqlite"}:
        return normalized
    raise ValueError(
        "WOOBE_DATABASE_URL must be PostgreSQL for runtime deployments or SQLite for tests"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="WOOBE_",
        env_file=".env",
        extra="ignore",
    )

    service_role: str = "api"
    edition: str = "core"

    database_url: str = "postgresql://postgres:postgres@localhost:5432/woobe"
    debug: bool = False
    secret_key: str = ""
    encryption_key: str = Field(default="", min_length=0)
    auth_issuer: str = "woobe"
    auth_audience: str = "woobe-web"
    access_token_ttl_seconds: int = Field(default=900, gt=0, le=3600)
    refresh_token_ttl_days: int = Field(default=30, gt=0, le=90)
    auth_clock_skew_seconds: int = Field(default=30, ge=0, le=300)
    access_cookie_name: str = "woobe_access"
    access_cookie_secure: bool = False
    access_cookie_same_site: str = "lax"
    refresh_cookie_name: str = "woobe_refresh"
    refresh_cookie_secure: bool = False
    refresh_cookie_same_site: str = "lax"
    csrf_cookie_name: str = "woobe_csrf"
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
    run_persistence_mode: str = "event_journal"
    mongodb_url: str | None = None
    mongodb_database: str = "woobe"
    run_event_durability_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    run_event_redis_stream: str = "woobe:runtime:journal:persistence"
    run_event_dead_letter_stream: str = "woobe:runtime:journal:dead"
    run_event_output_batch_bytes: int = Field(default=16384, ge=1024, le=1048576)
    run_event_output_flush_interval_ms: int = Field(default=200, ge=10, le=5000)
    default_context_manager: str = "stdcm:v3"
    chat_surface_enabled: bool = True
    chat_surface_allow_insecure_origins: bool = False
    chat_token_signing_key: str = ""
    chat_token_issuer: str = "woobe-chat"
    chat_token_audience: str = "woobe-chat-embed"
    chat_token_ttl_seconds: int = Field(default=900, ge=60, le=3600)
    chat_surface_session_create_rate_limit: int = Field(default=30, gt=0, le=10000)
    chat_surface_token_issue_rate_limit: int = Field(default=120, gt=0, le=10000)
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
    http_tool_timeout_max_ms: int = Field(default=30000, gt=0, le=120000)
    http_tool_response_max_bytes: int = Field(default=1048576, gt=0, le=16777216)
    http_tool_allow_local_networks: bool = False
    db_pool_size: int = Field(default=20, gt=0, le=200)
    db_max_overflow: int = Field(default=10, ge=0, le=200)
    cors_origins: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8081,http://127.0.0.1:8081"
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
    rabbitmq_url: str = "amqp://woobe:woobe@localhost:5672/"
    rabbitmq_exchange: str = "woobe.events"
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
    mcp_session_key_prefix: str = "woobe:mcp-session"
    mcp_session_ttl_seconds: int = Field(default=3600, gt=0, le=86400)
    outbox_batch_size: int = 50
    inbox_batch_size: int = 50
    outbox_lock_timeout_seconds: int = 300
    inbox_lock_timeout_seconds: int = 300
    outbox_max_retries: int = 3
    retry_base_delay_seconds: float = 1.0
    retry_max_delay_seconds: float = 300.0
    retry_backoff_multiplier: float = 2.0

    @field_validator("edition", mode="before")
    @classmethod
    def validate_edition(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized != "core":
            raise ValueError("WOOBE_EDITION must be 'core' in the Core distribution")
        return normalized

    @field_validator("run_persistence_mode", mode="before")
    @classmethod
    def validate_run_persistence_mode(cls, value: object) -> str:
        normalized = str(value).strip().lower()
        if normalized not in {"event_journal", "legacy_finalization"}:
            raise ValueError(
                "WOOBE_RUN_PERSISTENCE_MODE must be 'event_journal' or 'legacy_finalization'"
            )
        return normalized

    @field_validator("default_context_manager", mode="before")
    @classmethod
    def validate_default_context_manager(cls, value: object) -> str:
        normalized = str(value).strip()
        name, separator, version = normalized.partition(":")
        if (
            not separator
            or not name.strip()
            or not version.strip()
            or ":" in version
            or name.strip() == "default"
        ):
            raise ValueError(
                "WOOBE_DEFAULT_CONTEXT_MANAGER must identify a concrete strategy as '<name>:<version>'"
            )
        return f"{name.strip()}:{version.strip()}"

    @field_validator("database_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if isinstance(value, str):
            return _normalize_async_postgres_url(value)
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        return _validate_database_url(value)

    @field_validator("rabbitmq_url")
    @classmethod
    def validate_rabbitmq_url(cls, value: str) -> str:
        return _validate_connection_url(
            value,
            schemes={"amqp", "amqps"},
            variable="WOOBE_RABBITMQ_URL",
        )

    @field_validator("redis_url")
    @classmethod
    def validate_redis_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return _validate_connection_url(
            normalized,
            schemes={"redis", "rediss"},
            variable="WOOBE_REDIS_URL",
        )

    @field_validator("mongodb_url")
    @classmethod
    def validate_mongodb_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return _validate_connection_url(
            normalized,
            schemes={"mongodb", "mongodb+srv"},
            variable="WOOBE_MONGODB_URL",
        )

    @field_validator("mongodb_database")
    @classmethod
    def validate_mongodb_database(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or any(char in normalized for char in '/\\. "'):
            raise ValueError("WOOBE_MONGODB_DATABASE must be a valid MongoDB database name")
        return normalized

    @field_validator("s3_endpoint_url")
    @classmethod
    def validate_s3_endpoint_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        return _validate_connection_url(
            normalized,
            schemes={"http", "https"},
            variable="WOOBE_S3_ENDPOINT_URL",
        )

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
            ("woobe", "woobe"),
            ("guest", "guest"),
        }

    @model_validator(mode="after")
    def validate_service_requirements(self) -> Settings:
        role = self.service_role.strip().lower()
        if role not in {"api", "worker"}:
            raise ValueError("service_role must be 'api' or 'worker'")

        errors: list[str] = []
        if not self.database_url.strip():
            errors.append("WOOBE_DATABASE_URL is required")
        if len(self.encryption_key.strip()) < 16:
            errors.append("WOOBE_ENCRYPTION_KEY must contain at least 16 characters")
        if role == "api" and len(self.secret_key.strip()) < 32:
            errors.append("WOOBE_SECRET_KEY must contain at least 32 characters for API")
        if role == "worker" and not self.rabbitmq_url.strip():
            errors.append("WOOBE_RABBITMQ_URL is required for Workers")
        if self.storage_driver.strip().lower() == "s3" and not (self.s3_bucket or "").strip():
            errors.append("WOOBE_S3_BUCKET is required when WOOBE_STORAGE_DRIVER=s3")
        if errors:
            raise ValueError("; ".join(errors))
        return self

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

        role = self.service_role.strip().lower()
        errors: list[str] = []
        if self.debug:
            errors.append("WOOBE_DEBUG must be false in production")
        if self._is_weak_secret(self.encryption_key):
            errors.append("WOOBE_ENCRYPTION_KEY is weak or uses a known placeholder")
        if self._uses_default_credentials(self.database_url):
            errors.append("WOOBE_DATABASE_URL uses default credentials")
        if not self.json_logs:
            errors.append("WOOBE_JSON_LOGS must be true in production")

        if role == "api":
            if self._is_weak_secret(self.secret_key):
                errors.append("WOOBE_SECRET_KEY is weak or uses a known placeholder")
            if self.chat_surface_enabled:
                if self._is_weak_secret(self.chat_token_signing_key):
                    errors.append(
                        "WOOBE_CHAT_TOKEN_SIGNING_KEY is required and must be strong"
                    )
                elif self.chat_token_signing_key == self.secret_key:
                    errors.append(
                        "WOOBE_CHAT_TOKEN_SIGNING_KEY must differ from WOOBE_SECRET_KEY"
                    )
            if not self.access_cookie_secure:
                errors.append("WOOBE_ACCESS_COOKIE_SECURE must be true in production")
            if not self.refresh_cookie_secure:
                errors.append("WOOBE_REFRESH_COOKIE_SECURE must be true in production")

            origins = [item.strip() for item in self.cors_origins.split(",") if item.strip()]
            if not origins or "*" in origins:
                errors.append("WOOBE_CORS_ORIGINS must contain exact origins")
            if any(origin.startswith("http://") for origin in origins):
                errors.append("WOOBE_CORS_ORIGINS must use HTTPS in production")

            trusted_hosts = [
                item.strip() for item in self.trusted_hosts.split(",") if item.strip()
            ]
            if not trusted_hosts or "*" in trusted_hosts:
                errors.append("WOOBE_TRUSTED_HOSTS must contain exact hostnames")
        elif role == "worker" and self._uses_default_credentials(self.rabbitmq_url):
            errors.append("WOOBE_RABBITMQ_URL uses default credentials")

        if errors:
            raise ValueError("; ".join(errors))
        return self
