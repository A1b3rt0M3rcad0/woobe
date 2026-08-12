# Upgrading Woobe Community

Woobe Community uses the root `compose.yml` as its supported self-host topology.

## Before upgrading

1. Read the release notes and migration compatibility notes for the target version.
2. Back up PostgreSQL using the documented backup procedure.
3. Back up the local Knowledge upload volume when local storage is enabled.
4. Record the currently deployed source/image version so the application deployment can be restored if necessary.

Do not assume that rolling an application version back also makes a database downgrade safe.

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
