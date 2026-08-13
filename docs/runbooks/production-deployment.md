# Woobe Community production deployment

## Deployment contract

The root `compose.yaml` is the supported Woobe Community self-host topology. Production is selected through configuration (`WOOBE_ENVIRONMENT=production`), not through a separate production Compose file.

The default single-host topology contains:

```text
db
rabbitmq
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
WOOBE_ENVIRONMENT=production
WOOBE_SECRET_KEY=<strong random secret>
WOOBE_ENCRYPTION_KEY=<different strong random secret>
WOOBE_CHAT_TOKEN_SIGNING_KEY=<third strong random secret>
WOOBE_ACCESS_COOKIE_SECURE=true
WOOBE_REFRESH_COOKIE_SECURE=true
WOOBE_CORS_ORIGINS=https://app.example.com,https://chat.example.com
WOOBE_TRUSTED_HOSTS=api.example.com
VITE_API_URL=https://api.example.com
VITE_CHAT_EMBED_URL=https://chat.example.com
```

Terminate TLS before the exposed services. Do not expose PostgreSQL or RabbitMQ to the public network. Keep generated `.env`, provider credentials, Tool credentials, Runtime Keys, and ChatSurface Access Keys outside source control.

## Rollout

Generate configuration once for a fresh installation, then replace local/public endpoint values with the actual production domains:

```bash
python scripts/generate_self_host_env.py
```

Build application artifacts:

```bash
docker compose build
```

Start durable infrastructure, run migrations explicitly, and then start application services:

```bash
docker compose up -d db rabbitmq
docker compose run --rm migrate
docker compose up -d api workers web chat-embed
```

Verify `/live`, `/ready`, Web, `/chat/v1/health`, and representative Agent/Network execution. `scripts/smoke_production.sh` contains the integrated HTTP smoke contract used by the repository's manual acceptance workflow.

## Storage and recovery

The supported Community topology uses persistent local Knowledge storage. PostgreSQL and the `woobe_uploads` volume must be part of the same backup/recovery plan.

Configuration hooks for external PostgreSQL, RabbitMQ, Redis, or S3-compatible services do not by themselves create an officially supported distributed topology. The Community MVP does not currently publish a separate external-infrastructure Compose contract.

## Rollback

Platform deployment rollback is image/source rollback and is separate from Agent/Network Release rollback inside Woobe. Do not run Alembic downgrade automatically because an application artifact is rolled back. Follow release-specific schema compatibility notes and restore a tested backup when required.

## Release evidence

Before a public production release, intentionally execute the relevant manual backend, frontend, container, acceptance, and security workflows; review image vulnerability findings; verify backup/restore; and attach the relevant evidence to the release process.

Repository workflows are intentionally manual and are not started merely by opening a pull request.
