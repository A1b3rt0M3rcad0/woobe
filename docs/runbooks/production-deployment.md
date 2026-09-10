# Woobe Core production deployment

## Deployment contract

The root `compose.yaml` is the supported Woobe Core self-host topology. Production is selected through configuration (`WOOBE_ENVIRONMENT=production`), not through a separate production Compose file.

The default single-host topology contains:

```text
db
mongodb
rabbitmq
redis
migrate
api
workers
web
chat-embed
```

`deploy/dev/compose.yml` is a contributor-only extension and is not the production deployment contract.

## Production configuration

Set strong, independent secrets and exact public origins/hosts. At minimum:

```env
WOOBE_EDITION=core
WOOBE_ENVIRONMENT=production
WOOBE_RUN_PERSISTENCE_MODE=event_journal
WOOBE_MONGODB_URL=mongodb://mongodb:27017
WOOBE_MONGODB_DATABASE=woobe
WOOBE_SECRET_KEY=<strong random secret>
WOOBE_ENCRYPTION_KEY=<different strong random secret>
WOOBE_CHAT_TOKEN_SIGNING_KEY=<third strong random secret>
WOOBE_ACCESS_COOKIE_SECURE=true
WOOBE_REFRESH_COOKIE_SECURE=true
WOOBE_CORS_ORIGINS=https://app.example.com,https://chat.example.com
WOOBE_TRUSTED_HOSTS=api.example.com
VITE_API_URL=https://api.example.com
VITE_CHAT_EMBED_URL=https://chat.example.com
VITE_WOOBE_EDITION=core
```

Terminate TLS before the exposed services. Do not expose PostgreSQL, MongoDB, RabbitMQ or Redis to the public network. Keep generated `.env`, provider credentials, Tool credentials, Runtime Keys and ChatSurface Access Keys outside source control.

## Rollout

Generate configuration once for a fresh installation, then replace local/public endpoint values with the actual production domains:

```bash
python scripts/generate_self_host_env.py
```

Build application artifacts:

```bash
docker compose build
```

Start durable/runtime infrastructure, run migrations explicitly, and then start application services:

```bash
docker compose up -d db mongodb rabbitmq redis
docker compose run --rm migrate
docker compose up -d api workers web chat-embed
```

Verify `/live`, `/ready`, Web, `/chat/v1/health` and representative Agent/Network execution. `scripts/smoke_production.sh` contains the integrated HTTP smoke contract used by repository acceptance validation.

## Run journal durability

In `event_journal` mode, PostgreSQL remains the relational Run registry/read-model store, MongoDB is the durable incremental Run event journal/checkpoint store, and Redis is the hot runtime state plus the delivery buffer between execution and MongoDB.

The supported single-host Compose runs Redis with AOF enabled and `appendfsync=everysec`. This materially reduces the delivery-buffer loss window but still permits a bounded pre-Mongo loss window under abrupt host/storage failure. Do not describe Redis as the durable source of truth. Runtime events marked with a durability barrier only complete that barrier after MongoDB exposes a contiguous durable watermark through the requested sequence.

The Redis journal delivery stream is intentionally not subject to arbitrary `MAXLEN` trimming. Until ACK/watermark-aware compaction is implemented, monitor Redis memory and journal backlog and do not manually trim unacknowledged journal entries. A growing backlog is an operational fault to investigate, not data that can be discarded safely.

## Storage and recovery

The supported Core topology uses persistent local Knowledge storage. PostgreSQL, MongoDB and the `woobe_uploads` volume must be part of the same durable backup/recovery plan. Redis and RabbitMQ require operational recovery procedures, but neither substitutes for PostgreSQL/MongoDB durable state.

Until a repository-managed MongoDB backup helper is available, use the backup/restore mechanism appropriate to the MongoDB deployment and test it together with PostgreSQL and Knowledge restoration before production release.

Configuration hooks for external infrastructure do not by themselves create a separately supported deployment topology.

## Rollback

Platform deployment rollback is image/source rollback and is separate from Agent/Network Release rollback inside Woobe. Do not run Alembic downgrade automatically because an application artifact is rolled back. Follow release-specific schema compatibility notes and restore a tested backup when required.

`WOOBE_RUN_PERSISTENCE_MODE=legacy_finalization` is an explicit compatibility strategy, not an automatic failure fallback. Do not silently switch a Run configured for `event_journal` to legacy persistence when MongoDB or the journal worker is unavailable.

## Release evidence

Before a public production release, execute the required backend, frontend, container, acceptance and security validation; review image vulnerability findings and third-party license inventory; verify PostgreSQL/MongoDB/Knowledge backup and restore; and preserve the relevant release evidence.
