# Woobe production deployment runbook

## Deployment contracts

Woobe uses explicit connection URLs and `WOOBE_*` configuration. `docker-compose.yml` is the full integration/single-node topology. `docker-compose.community.yml` is the supported small self-host topology. `docker-compose.prod.yml` is an application-only hardened reference for deployments with external PostgreSQL, RabbitMQ, Redis and/or object storage.

Production application services are:

```text
migrate
api
workers
web
chat-embed
```

ChatSurface is part of the production topology; it is not a development-only service.

## Production configuration

Set at minimum:

```env
WOOBE_ENVIRONMENT=production
WOOBE_SECRET_KEY=<strong random secret>
WOOBE_ENCRYPTION_KEY=<different strong random secret>
WOOBE_CHAT_TOKEN_SIGNING_KEY=<third strong random secret>
WOOBE_DATABASE_URL=postgresql://...
WOOBE_POSTGRES_URL=postgresql://...
WOOBE_RABBITMQ_URL=amqps://...
WOOBE_ACCESS_COOKIE_SECURE=true
WOOBE_REFRESH_COOKIE_SECURE=true
WOOBE_CORS_ORIGINS=https://app.example.com,https://chat.example.com
WOOBE_TRUSTED_HOSTS=api.example.com
VITE_API_URL=https://api.example.com
VITE_CHAT_EMBED_URL=https://chat.example.com
```

`WOOBE_POSTGRES_URL` is the direct migration/database-maintenance endpoint. `WOOBE_DATABASE_URL` is the runtime endpoint used by API/Workers and may point at a pool/proxy. Do not expose database or broker ports publicly.

## Rollout

Run migrations explicitly before starting the new application version:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate
docker compose -f docker-compose.prod.yml up -d api workers web chat-embed
```

Verify `/live`, `/ready`, the Web Nginx health endpoint and `/chat/v1/health` on the ChatSurface service. For the integrated smoke contract, use `scripts/smoke_production.sh`.

## Object storage

Distributed deployments should use S3-compatible storage so API and Workers do not depend on a shared host filesystem. Community single-node may use the persistent local Knowledge volume documented in `docs/SELF_HOSTING.md`.

## Rollback

Platform deployment rollback is image/version rollback and is separate from Agent/Network Release rollback inside Woobe. Do not run Alembic downgrade automatically because an application image is rolled back. Follow release-specific schema compatibility notes and restore a tested backup when required.

## Release evidence

Before production promotion, intentionally run the manual backend/frontend/migration/container/release workflows, review HIGH/CRITICAL image findings, verify backup/restore and attach relevant evidence to the release/PR. CI is intentionally manual and is not started merely by opening a pull request.
