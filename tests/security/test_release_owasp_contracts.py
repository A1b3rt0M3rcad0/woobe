from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def manifest_keys(environment: str) -> set[str]:
    keys: set[str] = set()
    for raw_line in environment.splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#") and "=" in line:
            keys.add(line.split("=", maxsplit=1)[0])
    return keys


def settings_environment_keys() -> set[str]:
    tree = ast.parse(read("src/shared/infra/config/config.py"))
    settings_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "Settings")
    fields = {
        node.target.id
        for node in settings_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    fields.discard("service_role")
    return {f"WOOBE_{field.upper()}" for field in fields}


def test_production_frontend_has_required_browser_security_headers() -> None:
    nginx = read("web/nginx.conf")
    for header in (
        "X-Content-Type-Options",
        "X-Frame-Options",
        "Referrer-Policy",
        "Permissions-Policy",
        "Cross-Origin-Opener-Policy",
        "Content-Security-Policy",
    ):
        assert f"add_header {header}" in nginx
    assert "server_tokens off" in nginx
    assert "frame-ancestors 'none'" in nginx
    assert "connect-src 'self' __API_ORIGIN__" in nginx
    assert "proxy_pass http://api" not in nginx


def test_production_compose_is_application_only_hardened_and_chat_surface_complete() -> None:
    compose = read("docker-compose.prod.yml")
    for infrastructure_service in ("db", "pgbouncer", "rabbitmq", "redis", "minio"):
        assert f"\n  {infrastructure_service}:\n" not in compose
    for service in ("migrate", "api", "workers", "web", "chat-embed"):
        assert f"\n  {service}:\n" in compose
    assert "WOOBE_POSTGRES_URL" in compose
    assert "WOOBE_DATABASE_URL" in compose
    assert "WOOBE_RABBITMQ_URL" in compose
    assert "WOOBE_CHAT_TOKEN_SIGNING_KEY" in compose
    assert "VITE_API_URL" in compose
    assert "VITE_CHAT_EMBED_URL" in compose
    assert "WOOBE_SERVICE_ROLE" not in compose
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "./src:" not in compose


def test_environment_manifest_covers_settings_and_uses_woobe_namespace() -> None:
    environment = read(".env.example")
    for variable in (
        "WOOBE_EDITION=",
        "WOOBE_POSTGRES_URL=",
        "WOOBE_DATABASE_URL=",
        "WOOBE_RABBITMQ_URL=",
        "WOOBE_REDIS_URL=",
        "WOOBE_CHAT_TOKEN_SIGNING_KEY=",
        "WOOBE_S3_ENDPOINT_URL=",
        "VITE_API_URL=",
        "VITE_CHAT_EMBED_URL=",
    ):
        assert variable in environment
    assert "WOOBE_CORS_ORIGINS=*" not in environment
    assert "WOOBE_TRUSTED_HOSTS=*" not in environment
    missing = settings_environment_keys() - manifest_keys(environment)
    assert not missing, f"Settings fields missing from .env.example: {sorted(missing)}"


def test_compose_files_consume_woobe_manifest_variables() -> None:
    environment = read(".env.example")
    expected = {key for key in manifest_keys(environment) if key.startswith("WOOBE_")}
    # Not every bootstrap-only application variable belongs to every topology, but
    # each canonical application setting must be consumed by at least one supported Compose file.
    combined = read("docker-compose.yml") + read("docker-compose.prod.yml") + read("docker-compose.community.yml")
    missing = {key for key in expected if key not in combined}
    assert not missing, f"Compose distribution ignores manifest variables: {sorted(missing)}"


def test_frontend_build_contract_includes_api_chat_surface_and_edition() -> None:
    dockerfile = read("web/Dockerfile")
    assert "VITE_API_URL" in dockerfile
    assert "VITE_CHAT_EMBED_URL" in dockerfile
    assert "VITE_WOOBE_EDITION" in dockerfile


def test_runtime_security_matrix_covers_private_resource_families() -> None:
    matrix = read("tests/integration/security/test_tenant_authorization_postgres.py")
    for identifier in (
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
    ):
        assert f'("{identifier}",' in matrix
    assert "Resource not found" in matrix
    assert "authorize_api_key" in matrix
