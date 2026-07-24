from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def service_block(compose: str, service: str, next_service: str | None = None) -> str:
    start = f"\n  {service}:\n"
    assert start in compose, f"service {service!r} not found"
    remainder = compose.split(start, maxsplit=1)[1]
    if next_service is None:
        return remainder
    end = f"\n  {next_service}:\n"
    assert end in remainder, f"service boundary {next_service!r} not found"
    return remainder.split(end, maxsplit=1)[0]


def manifest_keys(environment: str) -> set[str]:
    keys: set[str] = set()
    for raw_line in environment.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", maxsplit=1)[0])
    return keys


def settings_environment_keys() -> set[str]:
    tree = ast.parse(read("src/shared/infra/config/config.py"))
    settings_class = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    fields = {
        node.target.id
        for node in settings_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    # Runtime role is intrinsic to main.py/worker_main.py, not deployment configuration.
    fields.discard("service_role")
    return {f"PROJECTRAI_{field.upper()}" for field in fields}


def test_production_frontend_has_required_browser_security_headers() -> None:
    nginx = read("web/nginx.conf")
    required = (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Content-Security-Policy",
    )
    for header in required:
        assert f"add_header {header}" in nginx
    assert "server_tokens off" in nginx
    assert "frame-ancestors 'none'" in nginx
    assert "connect-src 'self' __API_ORIGIN__" in nginx
    assert "proxy_pass http://api" not in nginx


def test_production_compose_is_application_only_and_hardened() -> None:
    compose = read("docker-compose.prod.yml")
    migrate_block = service_block(compose, "migrate", "api")
    api_block = service_block(compose, "api", "workers")
    worker_block = service_block(compose, "workers", "web")
    web_block = service_block(compose, "web")

    for infrastructure_service in ("db", "pgbouncer", "rabbitmq", "redis", "minio"):
        assert f"\n  {infrastructure_service}:\n" not in compose

    assert "PROJECTRAI_POSTGRES_URL" in migrate_block
    assert "PROJECTRAI_DATABASE_URL" in api_block
    assert "PROJECTRAI_RABBITMQ_URL" not in api_block
    assert "PROJECTRAI_DATABASE_URL" in worker_block
    assert "PROJECTRAI_RABBITMQ_URL" in worker_block
    assert "VITE_API_URL" in web_block
    assert "PROJECTRAI_SERVICE_ROLE" not in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "./src:" not in compose
    assert "uploads_data" not in compose


def test_environment_manifest_documents_url_boundaries_and_single_template() -> None:
    environment = read(".env.example")

    for section in (
        "# POSTGRESQL — DIRECT DATABASE",
        "# PGBOUNCER — RUNTIME DATABASE ENDPOINT",
        "# RABBITMQ",
        "# REDIS",
        "# OBJECT STORAGE — S3 COMPATIBLE",
        "# RUNTIME / NETWORK POLICY",
        "# API",
        "# WORKERS",
        "# WEB",
    ):
        assert section in environment

    for variable in (
        "PROJECTRAI_POSTGRES_URL=",
        "PROJECTRAI_DATABASE_URL=",
        "PROJECTRAI_RABBITMQ_URL=",
        "PROJECTRAI_REDIS_URL=",
        "PROJECTRAI_S3_ENDPOINT_URL=",
        "VITE_API_URL=",
    ):
        assert variable in environment

    assert "API and WORKERS must NOT use this URL directly" in environment
    assert "API does not require RabbitMQ to start" in environment
    assert "PROJECTRAI_STORAGE_DRIVER=s3" in environment
    assert "PROJECTRAI_CORS_ORIGINS=*" not in environment
    assert "PROJECTRAI_TRUSTED_HOSTS=*" not in environment
    assert "PROJECTRAI_SERVICE_ROLE=" not in environment

    gitignore = read(".gitignore")
    assert ".env*" in gitignore
    assert "!.env.example" in gitignore
    assert "!.env.production.example" not in gitignore
    assert "!.env.web.example" not in gitignore


def test_environment_manifest_covers_every_settings_field() -> None:
    environment = read(".env.example")
    missing = settings_environment_keys() - manifest_keys(environment)
    assert not missing, f"Settings fields missing from .env.example: {sorted(missing)}"


def test_local_compose_keeps_application_connections_url_driven() -> None:
    compose = read("docker-compose.yml")
    assert "DATABASE_URL: ${PROJECTRAI_POSTGRES_URL" in compose
    assert "PROJECTRAI_DATABASE_URL: ${PROJECTRAI_DATABASE_URL" in compose
    assert "PROJECTRAI_RABBITMQ_URL: ${PROJECTRAI_RABBITMQ_URL" in compose
    assert "PROJECTRAI_REDIS_URL: ${PROJECTRAI_REDIS_URL" in compose
    assert "PROJECTRAI_S3_ENDPOINT_URL: ${PROJECTRAI_S3_ENDPOINT_URL" in compose
    assert "VITE_API_URL: ${VITE_API_URL" in compose
    assert "PROJECTRAI_SERVICE_ROLE" not in compose
    assert "uploads_data" not in compose
    assert "minio:" in compose


def test_frontend_only_logs_request_details_in_development() -> None:
    client = read("web/src/lib/api/client.ts")
    assert "if (import.meta.env.DEV)" in client
    assert "Authorization" in client
    assert "console.log" in client
    assert "console.error" in client
    assert "clearToken()" in client


def test_runtime_security_acceptance_matrix_covers_private_resource_families() -> None:
    matrix = read("tests/integration/security/test_tenant_authorization_postgres.py")
    resource_identifiers = (
        "organization_id",
        "project_id",
        "api_key_id",
        "credential_id",
        "agent_id",
        "version_id",
        "collection_id",
        "link_id",
        "document_id",
        "tool_id",
        "session_id",
        "message_id",
        "trace_id",
    )
    for identifier in resource_identifiers:
        assert f'("{identifier}",' in matrix
    assert "Resource not found" in matrix
    assert "authorize_api_key" in matrix


def test_fake_provider_requires_no_external_secret_and_has_failure_modes() -> None:
    provider = read("tests/fakes/openai_provider.py")
    assert "OPENAI_API_KEY" not in provider
    for scenario in ("primary-fail", "timeout", "cancel", "tool"):
        assert scenario in provider
