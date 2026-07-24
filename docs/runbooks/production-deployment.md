# Production deployment runbook

## Scope and invariants

This runbook deploys the MVP with `docker-compose.prod.yml`. PostgreSQL, PgBouncer and RabbitMQ remain on an internal Docker network. Only the unprivileged web reverse proxy publishes a host port. TLS must terminate at the platform ingress or load balancer in front of that port; direct Internet exposure of plain HTTP is not supported.

Development and Production use the same environment-variable contract. PostgreSQL credentials come only from `POSTGRES_USER`, `POSTGRES_PASSWORD` and `POSTGRES_DB`. RabbitMQ credentials come only from `RABBITMQ_USER` and `RABBITMQ_PASSWORD`. Application URLs are derived by the shared container entrypoint.

The database topology is intentionally fixed:

- `migrate` connects directly to PostgreSQL at `db:5432`;
- `api` and `workers` connect through PgBouncer at `pgbouncer:6432`;
- PgBouncer connects to the same PostgreSQL using the same `POSTGRES_*` credentials;
- PgBouncer capacity can be tuned with `PGBOUNCER_*` without duplicating credentials.

For a real deployment, mirror the images to a registry and pin immutable digests through a reviewed Compose override. The base file keeps local build definitions and `projectrai-api:0.1.0` / `projectrai-web:0.1.0` tags so the production topology can also be validated locally.

## Required configuration

Start from the production template:

```bash
cp .env.production.example .env
```

Fill the required secret/domain values in `.env`, then store the resulting values in the deployment secret manager rather than Git. Production startup rejects debug mode, wildcard or HTTP CORS origins, wildcard trusted hosts, weak keys, default database/RabbitMQ credentials and non-JSON logging.

Required externally managed values:

- `PROJECTRAI_SECRET_KEY` and `PROJECTRAI_ENCRYPTION_KEY`: independent random values, at least 32 characters;
- exact HTTPS `PROJECTRAI_CORS_ORIGINS` and exact `PROJECTRAI_TRUSTED_HOSTS`;
- non-default `POSTGRES_PASSWORD` and `RABBITMQ_PASSWORD`;
- public `VITE_API_URL` used by the frontend build;
- a reviewed Compose override that pins immutable application image digests for a real release.

The normal PgBouncer starting policy is:

```text
PGBOUNCER_POOL_MODE=transaction
PGBOUNCER_MAX_CLIENT_CONN=200
PGBOUNCER_DEFAULT_POOL_SIZE=20
PGBOUNCER_RESERVE_POOL_SIZE=5
PGBOUNCER_MAX_DB_CONNECTIONS=30
```

Treat these values as deployment capacity settings, not application secrets. Increase them only from observed database/PgBouncer saturation and PostgreSQL capacity.

## Build and preflight

```bash
docker compose -f docker-compose.prod.yml build

docker image inspect projectrai-api:0.1.0 --format '{{.Config.User}}'
docker image inspect projectrai-web:0.1.0 --format '{{.Config.User}}'

docker compose -f docker-compose.prod.yml config --quiet
```

Both image user values must be non-empty and not `0`/`root`. Review the rendered Compose output and confirm that `db`, `pgbouncer` and `rabbitmq` have no host `ports` entries and that no service uses bind mounts.

## Deploy

1. Start stateful dependencies.
2. Run the migration service once and require exit code zero.
3. Start API, workers and web.
4. Run health and authenticated smoke checks.

```bash
COMPOSE="docker compose -f docker-compose.prod.yml"

$COMPOSE up -d db rabbitmq pgbouncer
$COMPOSE run --rm migrate
$COMPOSE up -d api workers web

PROJECTRAI_BASE_URL=https://app.example.com \
SMOKE_EMAIL="$SMOKE_EMAIL" \
SMOKE_PASSWORD="$SMOKE_PASSWORD" \
SMOKE_PROJECT_ID="$SMOKE_PROJECT_ID" \
./scripts/smoke_production.sh
```

For a single-host validation after `.env` is configured, the compact flow is:

```bash
docker compose -f docker-compose.prod.yml up --build -d
```

`/live` proves process liveness. `/ready` performs a bounded database check and returns 503 while the dependency is unavailable. The worker container health check verifies the PID 1 worker runtime remains active; worker loop failures are emitted as structured logs and metrics.

## Operational visibility

Application logs are JSON and include `request_id` and `correlation_id`. Incoming valid IDs are propagated; otherwise the API generates them. Sensitive values continue through the shared redaction filter.

The API exposes Prometheus text metrics on its internal `/metrics` endpoint. The public Nginx route intentionally does not proxy that endpoint. Scrape it from the application network. Metrics include HTTP request count/status/latency, TTFT, provider/tool/worker failures, queue lag/retry hooks and SQLAlchemy pool state.

RabbitMQ queue and dead-letter state remains private. Inspect it from the deployment host:

```bash
$COMPOSE exec rabbitmq rabbitmqctl list_queues \
  name messages_ready messages_unacknowledged consumers message_bytes
$COMPOSE exec rabbitmq rabbitmqctl list_exchanges name type durable
```

Alert initially on: `/ready` failures for 2 minutes, an unhealthy worker container, sustained queue growth, worker/provider/tool failure rate, HTTP 5xx rate and database pool exhaustion.

## Graceful shutdown

API and workers receive SIGTERM and have a 45-second grace period. During rollout, remove a replica from ingress before stopping it. Do not force-kill a process with an active SSE stream unless the grace period expires. Worker shutdown sets its stop event, cancels child tasks and closes RabbitMQ and database connections.

## Rollback

Application rollback is image-based. Create a reviewed `docker-compose.rollback.yml` that overrides the API and web images with the previous immutable digests, then run:

```bash
docker compose -f docker-compose.prod.yml -f docker-compose.rollback.yml up -d --no-deps api workers web
./scripts/smoke_production.sh
```

Do not automatically downgrade Alembic during an application rollback. Migrations in this MVP must be backward-compatible for at least one application version. A schema rollback requires a reviewed migration-specific procedure and a verified backup.

## Release gate

Before production promotion, attach evidence for image sizes, image users, SBOMs, vulnerability reports, Compose policy validation, two consecutive migration runs, reverse-proxy smoke, graceful shutdown and the latest restore drill. The `development-mvp -> development` promotion remains a separate human decision.
