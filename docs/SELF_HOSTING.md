# Self-hosting Woobe Community

Woobe Community runs without a required Woobe Cloud account or call-home dependency.

## Quick start

Requirements: Docker with Docker Compose and Python 3 for configuration generation.

```bash
python scripts/generate_self_host_env.py --force
docker compose -f docker-compose.community.yml up -d --build
```

The Community topology intentionally keeps the first install small: PostgreSQL, RabbitMQ, API, Workers, Web and Chat Embed. Knowledge files use a persistent local Docker volume. Redis, PgBouncer and S3-compatible storage remain available in the full/distributed topology when needed.

## First user

On a fresh Community database, `GET /identity/instance/status` reports an uninitialized instance. The first registration uses the dedicated bootstrap endpoint and atomically creates:

- the Instance Owner;
- the initial Organization;
- the Organization owner membership;
- the authentication session;
- singleton instance settings.

After bootstrap, Community defaults to `invite_only`. Registration remains possible for emails with an active Organization invite, but arbitrary public registration is rejected by the backend.

## Existing databases

A database that already contains users is never assigned an Instance Owner automatically. After applying migration `0060`, initialize it explicitly:

```bash
PYTHONPATH=src uv run python scripts/bootstrap_existing_instance.py \
  --owner-email owner@example.com
```

The selected user must already be an active Organization owner.

## Production exposure

Before exposing Woobe to the internet, change the generated development defaults:

```text
WOOBE_ENVIRONMENT=production
WOOBE_ACCESS_COOKIE_SECURE=true
WOOBE_REFRESH_COOKIE_SECURE=true
WOOBE_CORS_ORIGINS=https://your-ui.example
WOOBE_TRUSTED_HOSTS=api.example
VITE_API_URL=https://api.example
VITE_CHAT_EMBED_URL=https://chat.example
```

Terminate TLS at a reverse proxy or load balancer. Do not expose PostgreSQL or RabbitMQ publicly.

Production validation rejects weak application secrets, default database credentials, insecure auth cookies, wildcard CORS/Trusted Hosts and a ChatSurface signing key that is weak or equal to the main auth signing key.

## Persistent data

The Community Compose persists:

- PostgreSQL data in `woobe_postgres`;
- RabbitMQ data in `woobe_rabbitmq`;
- Knowledge uploads in `woobe_uploads`.

Do not use `docker compose down -v` unless you intentionally want to destroy these volumes.

## Backup

Database backup:

```bash
WOOBE_POSTGRES_URL='postgresql://...' BACKUP_DIR=./backups \
  sh scripts/backup_postgres.sh
```

If using local Knowledge storage, back up the `woobe_uploads` volume together with the database so document metadata and physical files remain consistent.

## Restore

Restore into an isolated database first when possible. The restore script requires an explicit confirmation value:

```bash
RESTORE_FILE=/backups/woobe-....dump \
RESTORE_CONFIRM=restore-woobe \
WOOBE_POSTGRES_URL='postgresql://...' \
sh scripts/restore_postgres.sh
```

See `docs/UPGRADING.md` before changing versions.
