# Upgrading Woobe Community

Woobe Community uses the root `compose.yaml` as its supported self-host topology.

## Before upgrading

1. Read the release notes and migration compatibility notes for the target version.
2. Back up PostgreSQL using the documented backup procedure.
3. Back up the local Knowledge upload volume when local storage is enabled.
4. Record the currently deployed source/image version so the application deployment can be restored if necessary.

Do not assume that rolling an application version back also makes a database downgrade safe.

## Configuration namespace migration

Woobe renamed its application environment-variable namespace from `PROJECTRAI_*` to `WOOBE_*`.
Existing installations must migrate their application configuration before starting a version that uses the `WOOBE_` namespace.

For application variables, preserve the deployed value and rename the prefix:

```text
PROJECTRAI_SECRET_KEY          -> WOOBE_SECRET_KEY
PROJECTRAI_ENCRYPTION_KEY      -> WOOBE_ENCRYPTION_KEY
PROJECTRAI_DATABASE_URL        -> WOOBE_DATABASE_URL
PROJECTRAI_POSTGRES_URL        -> WOOBE_POSTGRES_URL
PROJECTRAI_RABBITMQ_URL        -> WOOBE_RABBITMQ_URL
PROJECTRAI_REDIS_URL           -> WOOBE_REDIS_URL
PROJECTRAI_CORS_ORIGINS        -> WOOBE_CORS_ORIGINS
PROJECTRAI_TRUSTED_HOSTS       -> WOOBE_TRUSTED_HOSTS
```

The same rule applies to the remaining application settings previously prefixed with `PROJECTRAI_`: rename only the prefix to `WOOBE_` and preserve the configured value unless the target release notes explicitly document a value change.

Infrastructure/bootstrap variables that never used the `PROJECTRAI_` prefix, including `POSTGRES_*`, `RABBITMQ_*`, `AWS_*` and `VITE_*`, are not part of this prefix migration.

Do not replace an existing production `.env` with a freshly generated one. Doing so can rotate signing or encryption material and can change infrastructure credentials. Migrate the existing configuration, compare it with the target version's `.env.example`, then rebuild and restart.

## Source-based upgrade

For a source checkout, update to the intended version and rebuild the artifacts:

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
```

When `VITE_*` public configuration changes, rebuilding Web is mandatory because those values are build-time configuration.

## Rollback

Application rollback and Agent/Network Release rollback are different operations.

- **Product Release rollback** inside Woobe restores a previously published immutable Agent or Network Release.
- **Platform deployment rollback** restores a previous Woobe application artifact/source version.

Do not automatically execute `alembic downgrade` merely because an application artifact is rolled back. Use the release-specific schema compatibility notes and a tested backup/restore path when database recovery is required.
