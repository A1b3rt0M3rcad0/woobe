from __future__ import annotations

import argparse
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote


def set_value(content: str, key: str, value: str) -> str:
    lines = content.splitlines()
    prefix = f"{key}="
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = f"{key}={value}"
            replaced = True
            break
    if not replaced:
        lines.append(f"{key}={value}")
    return "\n".join(lines) + "\n"


def generate(template: Path, output: Path, *, force: bool) -> None:
    if output.exists() and not force:
        raise SystemExit(f"Refusing to overwrite {output}; pass --force to replace it")
    content = template.read_text(encoding="utf-8")

    db_user = "woobe"
    db_password = token_urlsafe(24)
    rabbit_user = "woobe"
    rabbit_password = token_urlsafe(24)

    values = {
        "WOOBE_EDITION": "core",
        "WOOBE_SECRET_KEY": token_urlsafe(48),
        "WOOBE_ENCRYPTION_KEY": token_urlsafe(48),
        "WOOBE_CHAT_TOKEN_SIGNING_KEY": token_urlsafe(48),
        "POSTGRES_USER": db_user,
        "POSTGRES_PASSWORD": db_password,
        "POSTGRES_DB": "woobe",
        "WOOBE_POSTGRES_URL": f"postgresql://{quote(db_user)}:{quote(db_password)}@db:5432/woobe",
        "WOOBE_DATABASE_URL": f"postgresql://{quote(db_user)}:{quote(db_password)}@db:5432/woobe",
        "RABBITMQ_USER": rabbit_user,
        "RABBITMQ_PASSWORD": rabbit_password,
        "WOOBE_RABBITMQ_URL": f"amqp://{quote(rabbit_user)}:{quote(rabbit_password)}@rabbitmq:5672/",
        "WOOBE_REDIS_URL": "",
        "WOOBE_RUN_PERSISTENCE_MODE": "event_journal",
        "WOOBE_MONGODB_URL": "mongodb://mongodb:27017",
        "WOOBE_MONGODB_DATABASE": "woobe",
        "WOOBE_MCP_SESSION_CACHE_ENABLED": "false",
        "WOOBE_DEFAULT_CONTEXT_MANAGER": "stdcm",
        "WOOBE_STORAGE_DRIVER": "local",
        "WOOBE_UPLOAD_LOCAL_DIR": "/app/storage/uploads",
        "WOOBE_PUBLIC_API_URL": "http://localhost:8000",
        "WOOBE_PUBLIC_CHAT_EMBED_URL": "http://localhost:8081",
        "VITE_API_URL": "http://localhost:8000",
        "VITE_CHAT_EMBED_URL": "http://localhost:8081",
        "VITE_WOOBE_EDITION": "core",
        "WOOBE_WEB_PORT": "8080",
        "WOOBE_CHAT_EMBED_PORT": "8081",
        "WOOBE_CORS_ORIGINS": "http://localhost:8080,http://127.0.0.1:8080,http://localhost:8081,http://127.0.0.1:8081",
        "WOOBE_TRUSTED_HOSTS": "localhost,127.0.0.1",
    }
    for key, value in values.items():
        content = set_value(content, key, value)
    output.write_text(content, encoding="utf-8")
    print(f"Generated {output} for Woobe Core self-hosting")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a Woobe Core .env with random secrets")
    parser.add_argument("--template", default=".env.example")
    parser.add_argument("--output", default=".env")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    generate(Path(args.template), Path(args.output), force=args.force)


if __name__ == "__main__":
    main()
