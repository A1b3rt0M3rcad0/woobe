# Upgrading Woobe Core

Woobe Core uses the root `compose.yaml` as its supported self-host topology.

## CI compatibility gate

Pull requests are validated against the most recent published platform tag reachable from the target branch. The Acceptance workflow initializes PostgreSQL with the previous release API image, preserves a persisted workspace probe, applies the PR's current migration image, runs Alembic consistency checks and confirms the persisted probe survives the upgrade.

This gate complements fresh-install migration tests. A green upgrade check means the tested previous-release schema can transition to the PR schema for that exact commit; release-specific migration notes are still required when operator action is necessary.

## Before upgrading

1. Read the release notes and migration compatibility notes for the target version.
2. Back up PostgreSQL using the documented backup procedure.
3. Back up Knowledge files or configured object-storage data.
4. Record the currently deployed source/image version and `.env`.

Do not assume that rolling an application version back also makes a database downgrade safe.

## Migration from the legacy ProjectRAI deployment contract

Treat an installation that still uses legacy `PROJECTRAI_*` configuration or historical Compose files as a deployment migration, not as a blind in-place restart.

Application settings previously named `PROJECTRAI_*` are now named `WOOBE_*`. Preserve existing signing/encryption keys and deliberately migrate service endpoints to the current topology.

## Source-based upgrade

```bash
docker compose build
docker compose run --rm migrate
docker compose up -d api workers web chat-embed
```

Verify API readiness, Web UI, ChatSurface, Workers, representative Agent/Network execution and Knowledge document access.

When `VITE_*` public configuration changes, rebuilding Web is mandatory because those values are build-time configuration.

## Rollback

Application rollback and Agent/Network Release rollback are different operations.

- Product Release rollback restores a previously published immutable Agent or Network Release.
- Platform deployment rollback restores a previous Woobe application artifact/source version.

Do not automatically execute `alembic downgrade` merely because an application artifact is rolled back. Use release-specific schema compatibility notes and a tested backup/restore path.
