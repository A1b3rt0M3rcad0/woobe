# woobe-core

Product Core package for Woobe bounded contexts, domain and application code, shared technical infrastructure, runtime contracts and bounded-context presentation/composition code.

`woobe-core` is intentionally a product Core package rather than a framework-neutral library. Module-local routers, controllers, schemas and composers remain colocated with the bounded context that owns them. Process composition roots do not belong here.

Alembic configuration and migration history are owned by Core at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`.

Dependency rule: `woobe-api` and `woobe-workers` may depend on `woobe-core`; `woobe-core` must not depend on `woobe-api`, `woobe-workers` or Enterprise implementation.

## License

`woobe-core` is licensed under the **Woobe Core Sustainable Use License 1.0** in the repository-root `LICENSE.md`, except third-party components or files carrying their own license notice.

See `docs/adr/0004-package-workspace-and-process-boundaries.md`.
