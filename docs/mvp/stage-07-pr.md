# MVP-07 pull request notes

Base: `development-mvp`
Head: `chore/mvp-07-production-deployment`

## Summary

- multi-stage non-root backend and frontend images;
- Nginx SPA/reverse-proxy production runtime;
- isolated production Compose topology with PgBouncer and one-shot migrations;
- production configuration fail-fast checks;
- liveness, readiness, structured logs, request correlation and runtime metrics;
- PostgreSQL backup/restore commands and operations runbooks;
- production container policy, SBOM and vulnerability evidence workflow.

## Required checks before merge

- backend and frontend suites;
- migrations from an empty database and a second idempotent upgrade;
- production image builds and non-root inspection;
- production Compose policy workflow;
- runtime smoke and graceful shutdown;
- staging restore drill evidence.

## Rollback

Roll back API/web images using immutable previous digests. Do not automatically downgrade Alembic; use a reviewed migration-specific rollback with a verified backup.
