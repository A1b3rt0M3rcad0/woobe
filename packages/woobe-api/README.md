# woobe-api

Process package for Woobe's HTTP boundary. FastAPI application bootstrap, process-level middleware, transport registration and public HTTP entrypoints belong here.

Bounded-context routers, controllers, schemas and composers remain colocated with their owning module in `woobe-core`; this package composes those transport adapters into the running API process.

`woobe-api` may depend on `woobe-core`; `woobe-core` must never depend on this package.

## Published container

The deployable image is `ghcr.io/a1b3rt0m3rcad0/woobe-api:<VERSION>`. It exposes port `8000` and requires the Woobe runtime infrastructure and environment configuration to be supplied by the deployment.

See [`docs/runbooks/container-packages.md`](../../docs/runbooks/container-packages.md) for pull, migration, environment, storage and standalone run examples.

## License

`woobe-api` is part of Woobe Core and is licensed under the **Woobe Core Sustainable Use License 1.0** in repository-root `LICENSE.md`, except third-party components or files carrying their own license notice.
