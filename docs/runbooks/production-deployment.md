# Production deployment runbook

## Scope and invariants

ProjectRAI/Woobe uses one deployment contract for development, staging and production: `.env.example`.

The application must not infer where PostgreSQL, PgBouncer, RabbitMQ, Redis, object storage or the Web/API are running. Communication between services is expressed through explicit URLs in the deployment manifest.

`docker-compose.yml` is the full-stack integration/single-node harness. It can provision PostgreSQL, PgBouncer, RabbitMQ, Redis and MinIO locally, but those service names are not application defaults.

`docker-compose.prod.yml` is an application-only hardened reference containing `migrate`, `api`, `workers` and `web`. It assumes dependency endpoints are externally reachable and configured in `.env`. A real deployment may instead run the same images through Kubernetes, ECS, Nomad, independent Docker hosts or VMs.

## Single environment manifest

Start from:

```bash
cp .env.example .env
```

Do not create a different variable schema for Production. Change only deployment values/endpoints and set:

```env
PROJECTRAI_ENVIRONMENT=production
```

The manifest is organized by service and documents who consumes each endpoint.

Primary connection boundaries:

```text
PROJECTRAI_POSTGRES_URL
  PostgreSQL direct endpoint
  consumers: migration + PgBouncer

PROJECTRAI_DATABASE_URL
  pooled/runtime PostgreSQL endpoint
  consumers: API + Workers

PROJECTRAI_RABBITMQ_URL
  broker endpoint
  consumer: Workers

PROJECTRAI_REDIS_URL
  Redis endpoint
  consumers: Redis-backed API/Worker features

PROJECTRAI_S3_ENDPOINT_URL + bucket/credentials
  object storage
  consumers: API + Workers

VITE_API_URL
  public API endpoint embedded in the browser bundle
```

For PostgreSQL specifically:

```text
Migration ───── PROJECTRAI_POSTGRES_URL ─────► PostgreSQL
PgBouncer ───── PROJECTRAI_POSTGRES_URL ─────► PostgreSQL
API ─────────── PROJECTRAI_DATABASE_URL ─────► PgBouncer/pool
Workers ─────── PROJECTRAI_DATABASE_URL ─────► PgBouncer/pool
```

API and Workers must not use the direct migration/PostgreSQL URL.

## Service-specific configuration

`.env` is a deployment manifest, not a requirement to inject every variable into every process.

The Compose files deliberately pass only the variables a service consumes. The same rule should be applied to Kubernetes Secrets, ECS task definitions, systemd units or standalone `docker run` deployments.

API and Worker determine their runtime role from their own entrypoints (`src.main` and `src.worker_main`). There is no `PROJECTRAI_SERVICE_ROLE` deployment variable.

### API

Requires at minimum:

- `PROJECTRAI_DATABASE_URL`;
- `PROJECTRAI_REDIS_URL` when Redis-backed features are enabled;
- object-storage settings;
- `PROJECTRAI_SECRET_KEY`;
- `PROJECTRAI_ENCRYPTION_KEY`;
- API/CORS/cookie configuration.

API does not require `PROJECTRAI_RABBITMQ_URL` to start.

### Workers

Requires at minimum:

- `PROJECTRAI_DATABASE_URL`;
- `PROJECTRAI_RABBITMQ_URL`;
- `PROJECTRAI_REDIS_URL` when enabled;
- object-storage settings;
- `PROJECTRAI_ENCRYPTION_KEY`.

### Migration

Requires only the direct database boundary:

```env
PROJECTRAI_POSTGRES_URL=postgresql://...
```

Migration is an explicit deployment job. Application container startup never runs Alembic implicitly.

### PgBouncer

The bundled PgBouncer container consumes `PROJECTRAI_POSTGRES_URL` as its upstream `DATABASE_URL` and exposes the endpoint represented by `PROJECTRAI_DATABASE_URL` to application runtimes.

Baseline capacity values:

```text
PGBOUNCER_POOL_MODE=transaction
PGBOUNCER_MAX_CLIENT_CONN=200
PGBOUNCER_DEFAULT_POOL_SIZE=20
PGBOUNCER_RESERVE_POOL_SIZE=5
PGBOUNCER_MAX_DB_CONNECTIONS=30
```

These are capacity settings, not application connection settings.

## Bundled infrastructure bootstrap variables

`POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `RABBITMQ_USER` and `RABBITMQ_PASSWORD` exist only for the infrastructure containers in the full-stack Compose harness.

When PostgreSQL/RabbitMQ are externally managed, API/Workers/Migration do not need those bootstrap variables. They receive only their connection URLs.

For the bundled local stack, keep bootstrap credentials aligned with the URLs in `.env`.

## Object storage

Local development uses S3-compatible MinIO through the same `s3` storage driver used by distributed deployments.

```text
Development:
API/Workers ─► MinIO

Production:
API/Workers ─► S3 / R2 / managed S3-compatible storage
```

This avoids any dependency on a shared Docker filesystem. API and Workers may therefore run on different machines without losing access to uploaded Knowledge documents.

For AWS S3, normally leave `PROJECTRAI_S3_ENDPOINT_URL` empty and prefer IAM/workload identity rather than static `AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY`.

## Frontend

`VITE_API_URL` is part of the single `.env` manifest because it is a public connection endpoint, not a backend secret.

The Docker build receives only `VITE_API_URL` as a build argument. The complete `.env` is never mounted into the frontend build.

Local Vite uses the neutral `manifest` mode so legacy `.env.web` or `.env.production` files from older setups do not override the canonical root `.env`.

Nginx serves static SPA assets only. It does not proxy to a Docker service named `api`. The browser calls `VITE_API_URL` directly. If Production requires one public origin, route `/api` or API hostnames at the external ingress/load balancer.

## Production security values

Before setting `PROJECTRAI_ENVIRONMENT=production`, replace the local/example values:

- strong independent `PROJECTRAI_SECRET_KEY` and `PROJECTRAI_ENCRYPTION_KEY`;
- non-default database credentials in `PROJECTRAI_DATABASE_URL`;
- non-default RabbitMQ credentials in `PROJECTRAI_RABBITMQ_URL` for Workers;
- exact HTTPS `PROJECTRAI_CORS_ORIGINS`;
- exact `PROJECTRAI_TRUSTED_HOSTS`;
- secure access/refresh cookies;
- production object-storage endpoint/bucket/authentication;
- correct public `VITE_API_URL`.

Production runtime validation is service-aware: browser/API security rules apply to the API process; RabbitMQ credential validation applies to the Worker process.

## Full-stack local/integration deployment

```bash
cp .env.example .env
docker compose up --build -d
```

The full stack provides:

- API: `http://localhost:8000`;
- Web: `http://localhost:5173`;
- PostgreSQL: `localhost:5432`;
- PgBouncer: `localhost:6432`;
- RabbitMQ management: `http://localhost:15672`;
- Redis: `localhost:6379`;
- MinIO API: `http://localhost:9000`;
- MinIO console: `http://localhost:9001`.

This topology is a harness. Application configuration still uses explicit URLs, so moving any dependency to another host only requires changing `.env`.

## Application-only Production reference

With external dependencies configured in `.env`:

```bash
docker compose -f docker-compose.prod.yml config --quiet
docker compose -f docker-compose.prod.yml build
```

Run migration before application rollout:

```bash
docker compose -f docker-compose.prod.yml run --rm migrate
```

Then start the application services:

```bash
docker compose -f docker-compose.prod.yml up -d api workers web
```

For a fully distributed deployment, run each service independently with only its required subset of environment variables.

## Health semantics

- `/live`: API process is alive;
- `/health`: lightweight process health;
- `/ready`: bounded direct check through `PROJECTRAI_DATABASE_URL`; returns 503 while the runtime database endpoint is unavailable.

The full-stack PostgreSQL and PgBouncer healthchecks execute authenticated `SELECT 1` probes using their configured URLs.

Worker startup explicitly connects to its database and RabbitMQ dependencies before entering the worker loop.

## Backup and restore

Backup and restore scripts use the direct database endpoint rather than Docker host defaults:

```env
PROJECTRAI_POSTGRES_URL=postgresql://...
```

Example:

```bash
PROJECTRAI_POSTGRES_URL="$PROJECTRAI_POSTGRES_URL" ./scripts/backup_postgres.sh
```

Restore requires the same direct URL plus the existing explicit confirmation guard.

## Graceful shutdown

API and workers receive SIGTERM. During rollout, remove an API replica from ingress before stopping it. Do not force-kill an active runtime/SSE process unless its grace period expires.

## Rollback

Application rollback is image-based. Repoint API/Worker/Web to previous immutable image digests and run smoke checks again. Do not automatically downgrade Alembic during application rollback. MVP migrations must remain backward-compatible for at least one application version.

## Release gate

Before Production promotion, attach evidence for image users/sizes, SBOM/vulnerability reports, migration success, API readiness, smoke tests, graceful shutdown and database backup/restore procedures.
