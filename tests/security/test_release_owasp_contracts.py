from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_production_proxy_has_required_browser_security_headers() -> None:
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
    assert "proxy_buffering off" in nginx


def test_production_topology_does_not_publish_data_services_or_bind_mount_source() -> None:
    compose = read("docker-compose.prod.yml")
    db_block = compose.split("  db:\n", maxsplit=1)[1].split("  pgbouncer:\n", maxsplit=1)[0]
    pgbouncer_block = compose.split("  pgbouncer:\n", maxsplit=1)[1].split("  rabbitmq:\n", maxsplit=1)[0]
    rabbit_block = compose.split("  rabbitmq:\n", maxsplit=1)[1].split("\nnetworks:\n", maxsplit=1)[0]

    assert "ports:" not in db_block
    assert "ports:" not in pgbouncer_block
    assert "ports:" not in rabbit_block
    assert "../" not in compose
    assert "./src:" not in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose


def test_production_environment_is_template_only_and_rejects_wildcard_origins() -> None:
    environment = read(".env.production.example")
    assert "Never commit .env.production" in environment
    assert "PROJECTRAI_SECRET_KEY=replace-with-at-least-32-random-characters" in environment
    assert "PROJECTRAI_ENCRYPTION_KEY=replace-with-at-least-32-random-characters" in environment
    assert "PROJECTRAI_CORS_ORIGINS=*" not in environment
    assert "PROJECTRAI_TRUSTED_HOSTS=*" not in environment

    gitignore = read(".gitignore")
    assert ".env*" in gitignore
    assert "!.env.production.example" in gitignore


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
