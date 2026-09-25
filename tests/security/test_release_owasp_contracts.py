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
    tree = ast.parse(
        read("packages/woobe-core/src/shared/infra/config/config.py")
    )
    settings_class = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Settings"
    )
    fields = {
        node.target.id
        for node in settings_class.body
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name)
    }
    fields.discard("service_role")
    return {f"WOOBE_{field.upper()}" for field in fields}


def test_production_frontend_has_required_browser_security_headers() -> None:
    nginx = read("packages/woobe-frontend/nginx.conf")
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


def test_default_core_compose_has_explicit_product_boundary() -> None:
    compose = read("compose.yaml")

    for service in (
        "db",
        "rabbitmq",
        "redis",
        "migrate",
        "api",
        "workers",
        "web",
        "chat-embed",
    ):
        assert f"\n  {service}:\n" in compose
    for optional_service in ("pgbouncer", "minio", "rabbitmq-observer"):
        assert f"\n  {optional_service}:\n" not in compose

    assert "WOOBE_REDIS_URL: redis://redis:6379/0" in compose
    assert "--appendonly" in compose
    assert '      - "yes"' in compose
    assert "--appendfsync" in compose
    assert "      - everysec" in compose
    assert '["CMD", "redis-cli", "ping"]' in compose

    assert "WOOBE_EDITION: core" in compose
    assert "WOOBE_STORAGE_DRIVER: local" in compose
    assert 'WOOBE_MCP_SESSION_CACHE_ENABLED: "true"' in compose
    assert "WOOBE_CHAT_TOKEN_SIGNING_KEY" in compose
    assert "WOOBE_PUBLIC_API_URL" in compose
    assert "WOOBE_PUBLIC_CHAT_EMBED_URL" in compose
    assert "no-new-privileges:true" in compose
    assert "./src:" not in compose


def test_legacy_compose_contracts_are_not_part_of_public_head() -> None:
    for path in (
        "docker-compose.yml",
        "docker-compose.community.yml",
        "docker-compose.prod.yml",
        "docker-compose.override.yml",
        "docker-compose.rabbitmq-observer.yml",
    ):
        assert not (ROOT / path).exists()


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
        "WOOBE_PUBLIC_API_URL=",
        "WOOBE_PUBLIC_CHAT_EMBED_URL=",
        "VITE_API_URL=",
        "VITE_CHAT_EMBED_URL=",
    ):
        assert variable in environment
    assert "WOOBE_CORS_ORIGINS=*" not in environment
    assert "WOOBE_TRUSTED_HOSTS=*" not in environment
    missing = settings_environment_keys() - manifest_keys(environment)
    assert not missing, f"Settings fields missing from .env.example: {sorted(missing)}"


def test_default_compose_uses_the_environment_manifest_explicitly() -> None:
    compose = read("compose.yaml")
    assert "env_file:" in compose
    assert "- .env" in compose
    for key in (
        "WOOBE_ENVIRONMENT",
        "WOOBE_DATABASE_URL",
        "WOOBE_ENCRYPTION_KEY",
        "WOOBE_RABBITMQ_URL",
        "WOOBE_SECRET_KEY",
        "WOOBE_CHAT_TOKEN_SIGNING_KEY",
        "WOOBE_CORS_ORIGINS",
        "WOOBE_TRUSTED_HOSTS",
    ):
        assert key in compose


def test_frontend_build_contract_includes_api_chat_surface_and_edition() -> None:
    dockerfile = read("packages/woobe-frontend/Dockerfile")
    assert "VITE_API_URL" in dockerfile
    assert "VITE_CHAT_EMBED_URL" in dockerfile
    assert "VITE_WOOBE_EDITION" in dockerfile
    assert "npm run build" in dockerfile
    assert "npm run test:run" not in dockerfile
    entrypoint = read("packages/woobe-frontend/docker-entrypoint.sh")
    assert "WOOBE_PUBLIC_API_URL" in entrypoint
    assert "WOOBE_PUBLIC_CHAT_EMBED_URL" in entrypoint
    assert "woobe-runtime-config.js" in entrypoint
    index = read("packages/woobe-frontend/index.html")
    assert "/runtime-config.js" in index
    assert 'org.opencontainers.image.licenses="LicenseRef-Woobe-Core-Sustainable-Use-1.0"' in dockerfile


def test_browser_image_builds_do_not_execute_test_suites() -> None:
    frontend = read("packages/woobe-frontend/Dockerfile")
    embed = read("packages/woobe-embed/Dockerfile")

    assert "RUN npm run build" in frontend.splitlines()
    assert "npm run test:run" not in frontend
    assert "RUN npm run build" in embed.splitlines()
    assert "npm run test" not in embed
    assert "npm run typecheck" not in embed
    assert r"\nRUN npm run build" not in embed


def test_runtime_security_matrix_covers_private_resource_families() -> None:
    matrix = read("tests/integration/security/test_tenant_authorization_postgres.py")
    for identifier in (
        "workspace_id",
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
