# woobe-api

Process package for Woobe's HTTP boundary. FastAPI application bootstrap, process-level middleware, transport registration, and public HTTP entrypoints belong here.

Bounded-context routers, controllers, schemas, and composers remain colocated with their owning module in `woobe-core`; this package composes those transport adapters into the running API process.

`woobe-api` may depend on `woobe-core`; `woobe-core` must never depend on this package.

See `docs/adr/0004-package-workspace-and-process-boundaries.md`.
