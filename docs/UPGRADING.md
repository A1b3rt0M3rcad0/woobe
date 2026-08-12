# Upgrading Woobe

Treat application version and database schema as separate deployment concerns.

## Before upgrading

1. Read the target release notes and migration notes.
2. Back up PostgreSQL.
3. Back up local Knowledge storage when `WOOBE_STORAGE_DRIVER=local`.
4. Record the currently running Woobe version and image/tag.

## Upgrade sequence

For source-based Community deployments:

```bash
git fetch --tags
git checkout <target-tag>
docker compose -f docker-compose.community.yml build
docker compose -f docker-compose.community.yml run --rm migrate
docker compose -f docker-compose.community.yml up -d
```

For image-based deployments, pull the exact target version before running the migration job.

## Rollback

Application rollback and database rollback are not the same operation. Do not automatically run Alembic downgrade in production simply because an application image is rolled back.

A release must document whether its schema is backward-compatible with the prior application version. When it is not, restore from a tested backup or follow the release-specific migration procedure.

Woobe Agent/Network rollback is a product runtime capability and is independent of rolling back the Woobe platform deployment itself.
