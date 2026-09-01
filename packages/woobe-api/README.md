# woobe-api

Process package for Woobe's HTTP boundary. FastAPI application bootstrap, process-level middleware, transport registration and public HTTP entrypoints belong here.

Bounded-context routers, controllers, schemas and composers remain colocated with their owning module in `woobe-core`; this package composes those transport adapters into the running API process.

`woobe-api` may depend on `woobe-core`; `woobe-core` must never depend on this package.

## License

`woobe-api` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice.
