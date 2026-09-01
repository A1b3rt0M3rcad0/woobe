# woobe-core

Community/Core package for Woobe bounded contexts, domain and application code, shared technical infrastructure, runtime contracts, and bounded-context presentation/composition code.

`woobe-core` is intentionally a product Core package rather than a framework-neutral library. Module-local routers, controllers, schemas, and composers remain colocated with the bounded context that owns them. Process composition roots do not belong here.

Alembic configuration and migration history remain owned by Core at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`. Extracting database migration execution into a separate package is outside this PR.

Dependency rule: `woobe-api` and `woobe-workers` may depend on `woobe-core`; `woobe-core` must not depend on `woobe-api`, `woobe-workers`, or Enterprise implementation.

See `docs/adr/0004-package-workspace-and-process-boundaries.md`.
