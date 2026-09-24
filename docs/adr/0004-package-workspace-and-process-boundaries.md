# ADR 0004 — Package workspace and process boundaries

Status: accepted for MVP.

Woobe separates three repository concerns explicitly: `packages/` contains product/distributable artifacts, `tooling/` contains engineering-only packages and quality tooling, and `tests/` contains repository-level and cross-system validation.

## Product packages

`packages/woobe-core` owns Core bounded contexts, domain and application code, shared technical infrastructure, runtime contracts, bounded-context presentation/composition code and the current Alembic migration surface.

`packages/woobe-api` owns the HTTP process composition root. Module-local routers, controllers, schemas and composers remain colocated with their bounded context in `woobe-core`.

`packages/woobe-workers` owns the worker process composition root. Concrete worker implementations remain with the bounded context that owns their behavior in Core.

`packages/woobe-frontend` owns the administrative control-plane frontend. `packages/woobe-embed` owns the independently built and deployed browser-facing ChatSurface artifact.

`packages/woobe-ee` is the separately licensed Enterprise product boundary. Core must not depend on Enterprise implementation.

Alembic configuration and migration history remain in `woobe-core` at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`.

## Licensing boundary

First-party packages outside the Enterprise Covered Paths, including the shared Runtime client and UI packages, are Core software under repository-root `LICENSE.md`, subject to third-party and brand exclusions. Enterprise material originally under `packages/woobe-ee/**`, and its copies, modifications and compiled forms, is excluded from the Core grant and governed by `LICENSE_EE.md`.

The Enterprise repository license permits defined non-production activities. Production Use requires a valid Enterprise authorization expressly granted by Woobe in writing. Independent Core integration code does not become Enterprise merely because it imports or invokes EE, and such integration grants no Enterprise production rights. This licensing distinction does not override the architectural dependency rules below.

Core does not expose an edition-specific integration package. Enterprise composition must consume public Core boundaries without reversing the dependency direction or making Core depend on Enterprise implementation.

## Engineering tooling

`tooling/woobe-testkit` contains shared test-only helpers. `tooling/woobe-mock` contains protocol mocks, simulators and fault-injection helpers. `tooling/quality-gate` contains the executable architecture quality gate and its policies.

Tooling may depend on product packages for validation. Product runtime packages must never depend on `tooling/`.

## System validation

`tests/` is the validation umbrella for repository architecture, contracts, integration, security and assembled-product behavior. End-to-end browser/full-stack validation lives at `tests/e2e/`.

## Dependency direction

```text
woobe-api ───────► woobe-core
woobe-workers ───► woobe-core
Enterprise ──────► woobe-core public boundaries

tooling/tests ───► product packages
```

The inverse dependencies are forbidden.
