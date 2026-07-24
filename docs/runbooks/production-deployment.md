# Production deployment runbook

## Scope and invariants

This runbook deploys the MVP with `docker-compose.prod.yml`. PostgreSQL, PgBouncer, RabbitMQ and Redis remain on the internal data network. Only the unprivileged web reverse proxy publishes a host port. TLS must terminate at the platform ingress or load balancer in front of that port; direct Internet exposure of plain HTTP is not supported.

Backend/infrastructure configuration and frontend build configuration are intentionally separated:

- `.env` contains backend and infrastructure settings/secrets;
- `.env.web` contains only public `VITE_*` frontend build values.

PostgreSQL credentials come only from `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`. RabbitMQ credentials come only from `RABBITMQ_USER` and `RABBITMQ_PASSWORD`. Application database/RabbitMQ URLs are derived by the shared container entrypoint.

The database topology is fixed:

- `migrate` connects directly to PostgreSQL at `db:5432`;
- `api` and `workers` connect through PgBouncer at `pgbouncer:6432`;
- PgBouncer uses the same `POSTGRES_*` credentials;
- PgBouncer capacity is tuned with `PGBOUNCER_*`, independently from credentials.

The single-host MVP topology uses a named `uploads_data` volume shared by API/workers for local Knowledge files. Multi-host or ephemeral deployments should switch `PROJECTRAI_STORAGE_DRIVER` to `s3` and configure the existing S3 settings instead of relying on that local volume.

For a real deployment, mirror images to a registry and pin immutable digests through a reviewed Compose override. The base file keeps local build definitions and `projectrai-api:0.1.0` / `projectrai-web:0.1.0` tags so the topology can also be validated locally.

## Required configuration

Start from the templates:

```bash
cp .env.production.example .env
cp .env.web.production.example .env.web
```

Fill the required values before deployment. Store the final `.env` in the deployment secret manager rather than Git. `.env.web` must contain only public `VITE_*` values and may never contain database, RabbitMQ, encryption or authentication secrets.

Required externally managed values:

- `PROJECTRAI_SECRET_KEY` and `PROJECTRAI_ENCRYPTION_KEY`: independent URL-safe random values, at least 32 characters;
- exact HTTPS `PROJECTRAI_CORS_ORIGINS` and exact `PROJECTRAI_TRUSTED_HOSTS`;
- non-default `POSTGRES_PASSWORD` and `RABBITMQ_PASSWORD`;
- public `VITE_API_URL` in `.env.web`;
- a reviewed Compose override pinning immutable application image digests for a real release.

Prefer URL-safe generated secrets, for example `secrets.token_urlsafe(...)`. If a manually chosen `.env` value contains `$`, single-quote the full value so Docker Compose does not interpolate it.

Production startup rejects debug mode, wildcard or HTTP CORS origins, wildcard trusted hosts, weak keys, default database/RabbitMQ credentials and non-JSON logging.

## PgBouncer baseline

```text
PGBOUNCER_POOL_MODE=transaction
PGBOUNCER_MAX_CLIENT_CONN=200
PGBOUNCER_DEFAULT_POOL_SIZE=20
PGBOUNCER_RESERVE_POOL_SIZE=5
PGBOUNCER_MAX_DB_CONNECTIONS=30
```

Treat these as capacity settings, not secrets. Increase them only from observed PgBouncer/PostgreSQL saturation and verified database capacity.

## Build and preflight

```bash
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build

docker image inspect projectrai-api:0.1.0 --format '{{.Config.User}}'
docker image inspect projectrai-web:0.1.0 --format '{{.Config.User}}'
```

Both image users must be non-empty and non-root. Review rendered Compose output and confirm that `db`, `pgbouncer`, `rabbitmq` and `redis` have no host `ports`, and that application source is not bind-mounted.

The PostgreSQL and PgBouncer healthchecks execute authenticated `SELECT 1` probes. A wrong password must therefore keep the dependency unhealthy rather than merely proving that its TCP listener is accepting connections.

## Deploy

1. Start stateful/runtime dependencies.
2. Run the migration service once and require exit code zero.
3. Start API, workers and web.
4. Run health and authenticated smoke checks.

```bash
COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE up -d db rabbitmq redis pgbouncer
$COMPOSE run --rm migrate
$COMPOSE up -d api workers web

PROJECTRAI_BASE_URL=https://app.example.com \
SMOKE_EMAIL="$SMOKE_EMAIL" \
SMOKE_PASSWORD="$SMOKE_PASSWORD" \
SMOKE_PROJECT_ID="$SMOKE_PROJECT_ID" \
./scripts/smoke_production.sh
```

`/live` proves process liveness. `/ready` performs a bounded database check and returns 503 while the dependency is unavailable. Worker health verifies the PID 1 worker runtime remains active.

## Operational visibility

Application logs are JSON and include request/correlation identifiers. Sensitive values continue through the shared redaction filter.

The API exposes Prometheus text metrics on its internal `/metrics` endpoint. The public Nginx route intentionally does not proxy that endpoint. Scrape it from the application network.

RabbitMQ queue state can be inspected from the deployment host:

```bash
$COMPOSE exec rabbitmq rabbitmqctl list_queues \
  name messages_ready messages_unacknowledged consumers message_bytes
$COMPOSE exec rabbitmq rabbitmqctl list_exchanges name type durable
```

Alert initially on `/ready` failures, unhealthy workers, sustained queue growth, provider/tool failures, HTTP 5xx rate, database pool exhaustion and persistent PgBouncer client waiting.

## Graceful shutdown

API and workers receive SIGTERM and have a 45-second grace period. During rollout, remove a replica from ingress before stopping it. Do not force-kill a process with an active SSE stream unless the grace period expires.

## Rollback

Application rollback is image-based. Create a reviewed `docker-compose.rollback.yml` that overrides API/web images with previous immutable digests, then run:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.rollback.yml up -d --no-deps api workers web
./scripts/smoke_production.sh
```

Do not automatically downgrade Alembic during application rollback. MVP migrations must remain backward-compatible for at least one application version. Schema rollback requires a reviewed migration-specific procedure and a verified backup.

## Release gate

Before Production promotion, attach evidence for image users/sizes, SBOMs, vulnerability reports, Compose policy validation, migrations, reverse-proxy smoke, graceful shutdown and the latest restore drill. The `development-mvp -> development` promotion remains a separate human decision.
