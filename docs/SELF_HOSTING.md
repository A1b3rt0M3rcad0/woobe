# Self-hosting Woobe Community

Woobe Community uses one supported default self-host contract: the root `compose.yaml`.

## First start

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

The generator creates `.env` from `.env.example` and replaces sensitive bootstrap values with independent random secrets. It refuses to overwrite an existing `.env` unless `--force` is explicitly supplied.

Default endpoints:

```text
Web UI:     http://localhost:8080
API:        http://localhost:8000
Chat Embed: http://localhost:8081
```

The first registration against a fresh Community database claims the instance atomically and creates the first Instance Owner and initial Workspace. Subsequent Community registration defaults to invite-only.

## Persistent state

The default topology persists:

```text
woobe_postgres   PostgreSQL application state
woobe_rabbitmq   RabbitMQ state
woobe_uploads    local Knowledge files
```

Back up PostgreSQL and the Knowledge upload volume together. Restoring only one side can leave document metadata and physical files inconsistent.

## Production configuration

Production is an environment configuration of the same Community topology, not a second Compose distribution.

Before public exposure, configure at least:

```env
WOOBE_ENVIRONMENT=production
WOOBE_SECRET_KEY=<strong random value>
WOOBE_ENCRYPTION_KEY=<different strong random value>
WOOBE_CHAT_TOKEN_SIGNING_KEY=<third strong random value>
WOOBE_ACCESS_COOKIE_SECURE=true
WOOBE_REFRESH_COOKIE_SECURE=true
WOOBE_CORS_ORIGINS=https://app.example.com,https://chat.example.com
WOOBE_TRUSTED_HOSTS=api.example.com
VITE_API_URL=https://api.example.com
VITE_CHAT_EMBED_URL=https://chat.example.com
```

Terminate TLS through a reverse proxy or ingress that you operate, expose only the required Web/API/Chat endpoints, and do not expose PostgreSQL or RabbitMQ publicly. Production settings reject weak or reused signing/encryption material and unsafe host/origin configuration.

After updating `.env`, rebuild Web when public `VITE_*` values change:

```bash
docker compose up -d --build
```

## Optional contributor topology

`deploy/dev/compose.yml` is an explicit contributor extension for exercising PgBouncer, Redis-backed MCP Session caching, and S3-compatible storage through MinIO.

```bash
docker compose -f compose.yaml -f deploy/dev/compose.yml up -d --build
```

It is not a second Community distribution and is not the production deployment contract.

## Distributed infrastructure

The application configuration supports explicit PostgreSQL, RabbitMQ, Redis, and S3-compatible connection settings, but Woobe does **not currently advertise a separate distributed/external-infrastructure deployment topology as part of the Community MVP support surface**.

Do not infer operational support, HA guarantees, upgrade guarantees, or an SLA from configuration hooks alone. Additional deployment topologies should become public contracts only when they are intentionally supported and tested as such.

## Backup and restore

Use the repository backup/restore procedures documented in [PostgreSQL backup and restore](runbooks/postgres-backup-restore.md). Include `woobe_uploads` in the same recovery plan.

Before an upgrade:

1. back up PostgreSQL;
2. back up Knowledge files;
3. record the currently deployed image/source version;
4. review migration and compatibility notes;
5. perform the upgrade;
6. verify API readiness, Web, ChatSurface, Workers, and representative runtime execution.

See [UPGRADING.md](UPGRADING.md).

## Security

Provider credentials, Tool credentials, Runtime Keys, ChatSurface Access Keys, session tokens, authentication secrets, encryption material, and database/broker credentials must be treated as secrets.

Never publish a generated `.env`. Review [SECURITY.md](../SECURITY.md) and the production deployment runbook before exposing a Community instance to the internet.
