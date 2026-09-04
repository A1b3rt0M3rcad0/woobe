# Woobe Architecture

Woobe is an API-first control plane and runtime for versioned AI products.

## Domain boundaries

Organization is the commercial account boundary. Project is the technical isolation boundary. Agents, Agent Networks, Tools, Knowledge, Runtime Keys, Runs and Traces are Project-scoped.

Agents are configurable definitions. Agent Releases are immutable snapshots. A Project may own multiple Agent Networks; each Network is a first-class entity with its own versions, releases, runs, sessions, traces and configuration. Network Releases are immutable snapshots of network composition. Draft is mutable, Staging is validation and Production consumes immutable releases.

Knowledge is organized around Collections and Documents. Vector Snapshots identify the exact generated knowledge set and indexing parameters used by runtime bindings.

## Execution model

An Agent Run is one logical execution of an Agent. A Network Run coordinates one or more causally related Agent Runs. Sessions preserve longitudinal conversational context; Runs represent finite execution occurrences; Traces are observable evidence of those Runs.

HTTP, streaming and async jobs are transport/delivery forms, not separate execution ontologies.

## Repository boundaries

```text
packages/                         # product / distributable artifacts
├── woobe-core/                   # Core bounded contexts, runtime contracts, shared infrastructure + migrations
├── woobe-api/                    # HTTP process composition root
├── woobe-workers/                # worker process composition root
├── woobe-runtime-client/         # shared browser Runtime protocol/observer primitives
├── woobe-frontend/               # administrative control-plane frontend
├── woobe-embed/                  # independently deployable ChatSurface embed
└── woobe-ee/                     # separately licensed Enterprise boundary

tooling/                          # engineering-only packages
├── woobe-testkit/
├── woobe-mock/
└── quality-gate/

tests/                            # repository and cross-system validation
├── architecture/
├── contract/
├── integration/
├── security/
└── e2e/
```

`woobe-core` is the transport-neutral product Core. Each bounded context owns its domain, application, infrastructure, presentation contracts and composition. FastAPI, Starlette, HTTP routes, middleware and HTTP response semantics are excluded from Core.

`woobe-api` is the real HTTP host and owns process-level HTTP composition. It may consume each bounded context only through that module's explicit `entrypoint.py`; persistence and repository access remain behind Core capabilities. `woobe-workers` owns process-level worker composition and consumes `entrypoint.py` or the intentionally narrow `background_boundary.py`. Core must not import either process package.

The canonical dependency direction is:

```text
woobe-api ----> module entrypoint ----> composition
                                        |----> presentation contracts
                                        |----> application ----> domain
                                        |----> infrastructure -> domain

woobe-workers -> entrypoint/background boundary
```

Application layers do not import infrastructure or transport frameworks. Composition is the only layer that assembles concrete implementations. HTTP routers do not open database sessions or instantiate repositories directly.

`woobe-runtime-client` owns transport-neutral browser-side Runtime protocol semantics such as SSE frame parsing, sequence/gap handling, replacement snapshots, terminal classification and retry policy. It does not own execution. `woobe-frontend` and `woobe-embed` consume it through their own transport/rendering adapters and remain independently deployable product artifacts.

`tooling/` is never part of the production dependency graph. `tests/` owns validation that spans package/repository/system boundaries.

Alembic configuration and migration history remain owned by `woobe-core` at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`.

## Runtime boundaries

Critical authorization, ownership, release immutability, duplicate-document rules, key scopes and runtime policy are enforced by the backend. The frontend reflects those rules but is not the security boundary.

PostgreSQL is the durable source of application state. RabbitMQ supports asynchronous work. Redis supports shared runtime coordination and execution recovery. Knowledge files use the configured storage provider.

## Core / Enterprise boundary

Core comprises `woobe-core`, `woobe-api`, `woobe-workers`, `woobe-runtime-client`, `woobe-frontend` and `woobe-embed` and is governed by repository-root `LICENSE.md`.

Enterprise is a separately licensed implementation boundary under `packages/woobe-ee`. Core must remain fully runnable without Enterprise implementation. The Core-side contract under `packages/woobe-core/src/editions/` is an interoperability seam, not a license switch.

See `LICENSE_EE.md` and `docs/adr/0004-package-workspace-and-process-boundaries.md`.
