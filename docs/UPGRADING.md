# Upgrading Woobe Community

Woobe Community uses the root `compose.yaml` as its supported self-host topology.

## Before upgrading

1. Read the release notes and migration compatibility notes for the target version.
2. Back up PostgreSQL using the documented backup procedure.
3. Back up Knowledge files or the object-storage data used by the current installation.
4. Record the currently deployed source/image version and `.env` so the application deployment can be restored if necessary.

Do not assume that rolling an application version back also makes a database downgrade safe.

## Migration from the legacy ProjectRAI deployment contract

The Community distribution changed both its application configuration namespace and its bundled self-host topology. Treat an installation that still uses the legacy `docker-compose.yml` / `PROJECTRAI_*` contract as a deployment migration, not as a blind in-place Compose restart.

The legacy bundled topology included PgBouncer, Redis and MinIO and used the Compose project name `projectrai`. The current root `compose.yaml` uses direct PostgreSQL for the bundled runtime, disables the Redis-backed MCP session cache by default, uses local persistent Knowledge storage by default, and uses the Compose project name `woobe`.

Because the Compose project name and volume names changed, existing PostgreSQL and MinIO data volumes are not automatically adopted by the new topology. Back up the old database and Knowledge/object-storage data first, start the target Community topology with reviewed configuration, and restore/migrate the data deliberately. Do not delete the old volumes until the upgraded installation has been verified.

### Environment-variable namespace

Application settings previously named `PROJECTRAI_*` are now named `WOOBE_*`.

For settings whose endpoint or semantics remain valid, preserve the deployed value and rename the prefix. Examples:

```text
PROJECTRAI_SECRET_KEY          -> WOOBE_SECRET_KEY
PROJECTRAI_ENCRYPTION_KEY      -> WOOBE_ENCRYPTION_KEY
PROJECTRAI_RABBITMQ_URL        -> WOOBE_RABBITMQ_URL
PROJECTRAI_CORS_ORIGINS        -> WOOBE_CORS_ORIGINS
PROJECTRAI_TRUSTED_HOSTS       -> WOOBE_TRUSTED_HOSTS
```

Preserve existing signing and encryption keys. Rotating those values accidentally during an upgrade can invalidate sessions or make persisted encrypted secrets unreadable.

Do **not** mechanically preserve legacy internal service URLs when moving from the old bundled topology. In particular:

```text
legacy PROJECTRAI_DATABASE_URL -> review and set WOOBE_DATABASE_URL for the target database endpoint
legacy PROJECTRAI_POSTGRES_URL -> review and set WOOBE_POSTGRES_URL for the target database endpoint
legacy PROJECTRAI_REDIS_URL    -> do not copy for the default Community topology; Redis is disabled there
legacy PROJECTRAI_S3_*         -> do not copy when adopting the default local-storage topology
```

A legacy URL such as `postgresql://...@pgbouncer:6432/...` is not valid in the current default Community Compose network because that topology no longer contains a `pgbouncer` service. The generated/current `.env.example` is the source of truth for target endpoints and defaults.

Infrastructure/bootstrap variables that never used the `PROJECTRAI_` prefix, including `POSTGRES_*`, `RABBITMQ_*`, `AWS_*` and `VITE_*`, are not renamed automatically. Review them against the target topology as well; credentials and database names must remain consistent with the data being restored.

Do not replace an existing production `.env` with a freshly generated one and then discard the old values. A generated file is appropriate as a target template, but secrets, credentials, origins and external endpoints from the existing deployment must be migrated deliberately.

## Source-based upgrade

After configuration and data migration have been prepared, update to the intended version and rebuild the artifacts:

```bash
docker compose build
```

Apply database migrations explicitly:

```bash
docker compose run --rm migrate
```

Then restart the application services:

```bash
docker compose up -d api workers web chat-embed
```

Verify:

```text
API /live
API /ready
Web UI
ChatSurface health/embed assets
Workers
representative Agent/Network execution
Knowledge document access
```

When `VITE_*` public configuration changes, rebuilding Web is mandatory because those values are build-time configuration.

## Rollback

Application rollback and Agent/Network Release rollback are different operations.

- **Product Release rollback** inside Woobe restores a previously published immutable Agent or Network Release.
- **Platform deployment rollback** restores a previous Woobe application artifact/source version.

For a legacy-topology migration, keep the original database/Knowledge backups and old deployment configuration until the new topology has passed verification. Do not automatically execute `alembic downgrade` merely because an application artifact is rolled back. Use release-specific schema compatibility notes and a tested backup/restore path when database recovery is required.
