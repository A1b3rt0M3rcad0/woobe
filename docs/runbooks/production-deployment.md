# Production deployment runbook

## Scope and invariants

This runbook deploys the MVP with `docker-compose.prod.yml`. PostgreSQL, PgBouncer and RabbitMQ remain on an internal Docker network. Only the unprivileged web reverse proxy publishes a host port. TLS must terminate at the platform ingress or load balancer in front of that port; direct Internet exposure of plain HTTP is not supported.

For a real deployment, mirror the images to a registry and pin immutable digests through a reviewed Compose override. The base file uses local `projectrai-api:0.1.0` and `projectrai-web:0.1.0` tags for staging validation.

## Required configuration

Copy `.env.production.example` outside the repository and replace every placeholder. Store the resulting values in the deployment secret manager, not in Git. Production startup rejects debug mode, wildcard or HTTP CORS origins, wildcard trusted hosts, weak keys, default database/RabbitMQ credentials and non-JSON logging.

Required externally managed values:

- `PROJECTRAI_SECRET_KEY` and `PROJECTRAI_ENCRYPTION_KEY`: independent random values, at least 32 characters.
- exact HTTPS `PROJECTRAI_CORS_ORIGINS` and exact `PROJECTRAI_TRUSTED_HOSTS`.
- non-default PostgreSQL and RabbitMQ credentials.
- a reviewed Compose override that pins immutable application image digests.

## Build and preflight

```bash
docker build --pull -t projectrai-api:0.1.0 .
docker build --pull -t projectrai-web:0.1.0 web

docker image inspect projectrai-api:0.1.0 --format '{{.Config.User}}'
docker image inspect projectrai-web:0.1.0 --format '{{.Config.User}}'

docker compose --env-file /run/secrets/projectrai.env \
  -f docker-compose.prod.yml config --quiet
```

Both image user values must be non-empty and not `0`/`root`. Review the rendered Compose output and confirm that `db`, `pgbouncer` and `rabbitmq` have no host `ports` entries and that no service uses bind mounts.

## Deploy

1. Start stateful dependencies.
2. Run the migration service once and require exit code zero.
3. Start API, workers and web.
4. Run health and authenticated smoke checks.

```bash
export ENV_FILE=/run/secrets/projectrai.env
COMPOSE="docker compose --env-file $ENV_FILE -f docker-compose.prod.yml"

$COMPOSE up -d db rabbitmq pgbouncer
$COMPOSE run --rm migrate
$COMPOSE up -d api workers web

PROJECTRAI_BASE_URL=https://app.example.com \
SMOKE_EMAIL="$SMOKE_EMAIL" \
SMOKE_PASSWORD="$SMOKE_PASSWORD" \
SMOKE_PROJECT_ID="$SMOKE_PROJECT_ID" \
./scripts/smoke_production.sh
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
