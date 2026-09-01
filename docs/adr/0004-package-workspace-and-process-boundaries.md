# ADR 0004 — Package workspace and process boundaries

Status: accepted for MVP.

Woobe separates three repository concerns explicitly: `packages/` contains product/distributable artifacts, `tooling/` contains engineering-only packages and quality tooling, and `tests/` contains repository-level and cross-system validation.

## Product packages

`packages/woobe-core` owns the Community bounded contexts, their domain and application code, shared technical infrastructure, runtime contracts, bounded-context presentation/composition code, and the current Alembic migration surface. `woobe-core` is a product Core package, not a framework-neutral library.

`packages/woobe-api` owns the HTTP process composition root: FastAPI application bootstrap, process-level middleware, transport registration, and public HTTP entrypoints. Module-local routers, controllers, schemas, and composers remain colocated with their bounded context in `woobe-core` so repository packaging does not split each business module across process packages.

`packages/woobe-workers` owns only the worker process composition root. Concrete worker implementations remain with the bounded context that owns their behavior under `woobe-core/src/modules/<module>/infra/workers/`. The worker process discovers and composes those implementations; Core must not import the Workers package.

`packages/woobe-frontend` owns the administrative control-plane frontend. `packages/woobe-embed` owns the independently built and deployed browser-facing ChatSurface embed artifact. Both consume HTTP/browser contracts rather than importing Python Core.

`packages/woobe-ee` is a reserved public boundary only; it contains no proprietary runtime implementation in the Community distribution.

Alembic configuration and migration history remain in `woobe-core`, at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`. A standalone database/migration package is not part of this repository cutover; if introduced, it requires a dedicated ADR/PR so runtime, deployment, packaging, and ownership consequences are evaluated independently.

## Engineering tooling

`tooling/woobe-testkit` contains shared test-only helpers. `tooling/woobe-mock` contains protocol mocks, simulators, and fault-injection helpers. `tooling/quality-gate` contains the executable architecture quality gate and its policies.

Tooling may depend on product packages for validation. Product runtime packages must never depend on `tooling/`.

## System validation

`tests/` is the validation umbrella for repository architecture, contracts, integration, security, and assembled-product behavior. End-to-end browser/full-stack validation lives at `tests/e2e/`; it is not a product package.

Tests may consume both `packages/` and `tooling/`. Production code must not import test or tooling packages.

## Dependency direction

The dependency direction is intentionally one-way: API and Workers may depend on Core; Core must not depend on API, Workers, or Enterprise implementation. Frontend and Embed consume HTTP contracts. Engineering tooling and tests may depend on product surfaces; the inverse dependency is forbidden.

Internal Python packages use package-level installation metadata. Runtime and backend-test images install the required internal packages as editable distributions instead of relying on repository-level `PYTHONPATH` for product package loading. The root dependency manifest and lock remain authoritative for the MVP; adopting a formal uv workspace lock is a separate change.

This decision favors small, operational boundaries over mechanically extracting every framework-facing file from Core. A stricter framework-neutral Core should be reconsidered only when independently reusable domain packages or multiple transport implementations create a concrete need for that split.
