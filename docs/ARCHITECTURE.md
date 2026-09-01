# Woobe Architecture

Woobe is an API-first control plane and runtime for versioned AI products.

## Domain boundaries

Workspace is the commercial/membership unit. Project is the technical isolation unit. Agents, Agent Networks, Tools, Knowledge, Runtime Keys, Runs, and Traces are Project-scoped.

Agents are configurable definitions. Agent Releases are immutable snapshots. A Project may own multiple Agent Networks; each Network is a first-class entity with its own versions, releases, runs, sessions, traces, and configuration. Network Releases are immutable snapshots of network composition. Draft is mutable, Staging is validation, and Production consumes immutable releases.

Knowledge is organized around Collections and Documents. Vector Snapshots identify the exact generated knowledge set and indexing parameters used by runtime bindings.

## Execution model

An Agent Run is one logical execution of an Agent. A Network Run coordinates one or more causally related Agent Runs. Sessions preserve longitudinal conversational context; Runs represent finite execution occurrences; Traces are observable evidence of those Runs.

HTTP, streaming, and async jobs are transport/delivery forms, not separate execution ontologies.

## Repository boundaries

Woobe separates product source, engineering tooling, and system validation:

```text
packages/                         # product / distributable artifacts
├── woobe-core/                   # bounded contexts, runtime contracts, shared infrastructure + migrations
├── woobe-api/                    # HTTP process composition root
├── woobe-workers/                # worker process composition root
├── woobe-frontend/               # administrative control-plane frontend
├── woobe-embed/                  # independently deployable ChatSurface embed
└── woobe-ee/                     # reserved Enterprise boundary

tooling/                          # engineering-only packages
├── woobe-testkit/                # shared test helpers
├── woobe-mock/                   # protocol mocks/fault injection
└── quality-gate/                 # executable architecture policies/checker

tests/                            # repository and cross-system validation
├── architecture/
├── contract/
├── integration/
├── security/
└── e2e/
```

`woobe-core` is a product Core package, not a framework-neutral library. Domain, application, infrastructure, and bounded-context presentation/composition code remain colocated with the module that owns the behavior. This includes module-local routers, controllers, schemas, and composers.

`woobe-api` owns process-level HTTP composition: FastAPI application bootstrap, middleware, transport registration, and public entrypoints. It may depend on Core. Core must not import API.

`woobe-workers` owns process-level worker composition. Concrete workers remain under the owning bounded context in `woobe-core/src/modules/<module>/infra/workers/`; the Workers process discovers and composes them. Core must not import Workers.

`woobe-frontend` and `woobe-embed` are separate product artifacts. The former is the control-plane UI; the latter is the browser-facing ChatSurface asset/runtime and can be built and deployed independently.

`tooling/` is never part of the production dependency graph. Testkit, mocks, and the architecture quality gate may consume product packages for validation, but product packages cannot depend on them.

`tests/` owns validation that spans package/repository/system boundaries. E2E belongs there because it validates the assembled product rather than providing a production artifact.

Alembic configuration and migration history remain owned by `woobe-core` at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`. Production migrations use this Core-owned migration surface before the API starts. Extracting migration execution into a separate database package is intentionally deferred to a dedicated change.

Internal Python boundaries use package-level installation metadata. Runtime and backend-test images install required internal packages as editable distributions while the root dependency manifest and lock remain authoritative for the MVP.

The durable decision is recorded in `docs/adr/0004-package-workspace-and-process-boundaries.md`.

## Runtime boundaries

Critical authorization, ownership, release immutability, duplicate-document rules, key scopes, and runtime policy are enforced by the backend. The frontend reflects those rules but is not the security boundary.

Runtime infrastructure is process-separated into API and Workers. RabbitMQ supports asynchronous module/runtime work. PostgreSQL is the durable source of application state. Redis supports shared runtime coordination where enabled. Knowledge files can use local persistent storage or S3-compatible storage.

## Distribution boundaries

The public repository and supported self-host distribution contain Woobe Community/Core only.

```text
Community  = Core distributed here
Cloud      = proprietary Woobe-managed product built on Core, not distributed here
Enterprise = reserved product boundary; no proprietary runtime implementation is distributed here
```

Community product code is rooted under `packages/`. Proprietary Cloud implementation is not part of the Community source tree or Community container build context. `packages/woobe-ee` is a reserved boundary marker and must not make Community depend on proprietary implementation.

Community composition roots include `packages/woobe-api/src/main.py`, `packages/woobe-workers/src/worker_main.py`, `packages/woobe-core/migrations/env.py`, the root `compose.yaml`, `packages/woobe-frontend`, and `packages/woobe-embed`. They must remain runnable without proprietary edition source.

Architecture tests under `tests/architecture/` protect package dependency direction, Community distribution boundaries, worker ownership, database ownership, migration ownership, tooling separation, and the absence of legacy root source trees.

The Community licensing and product boundary is described by `LICENSE.md` and `LICENSING.md`. Proprietary product terms are intentionally outside this repository.
