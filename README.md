# Woobe

> **Build agents like software.**
>
> The control plane between your product and AI engineering.

Woobe is an **API-first, source-available control plane and runtime for operating Agents and Agent Networks as production software**.

It gives teams one operational model to configure, version, release, execute, observe and govern AI products without coupling product code to mutable prompts, provider details, runtime orchestration or ad hoc infrastructure.

Production runs immutable, traceable releases. Development remains mutable. Runtime evidence records what actually executed.

> **Pre-release**
>
> Woobe is under active development toward its first public release. Public interfaces, deployment contracts and licensing text should be treated as pre-release until the release checklist is completed.

## What Woobe solves

Creating an Agent is not the same as operating an AI product.

A production team still needs to answer:

- Which Agent or Network version executed?
- Which prompt, model configuration, tools and knowledge were bound?
- Which immutable Release is active in Production?
- What happened during a Run?
- Which Session and Trace belong to that execution?
- Can Production be rolled back without reconstructing old mutable state?
- Can the AI layer evolve without forcing application code to become the operational control plane?

Woobe exists to own that operational layer.

```text
Configure
   ↓
Develop / Draft
   ↓
Validate in Staging
   ↓
Create immutable Release
   ↓
Activate in Production
   ↓
Run · Trace · Observe
   ↓
Rollback when needed
```

## Product model

| Concept | Responsibility |
| --- | --- |
| **Organization** | Commercial boundary. Owns plan, owner, members, limits and Projects. |
| **Project** | Technical isolation boundary. Agents, Networks, Tools, Knowledge, Runs, Sessions and Traces are Project-scoped. |
| **Agent** | Configurable AI unit with prompt, model configuration, tools, knowledge, output contract and runtime configuration. |
| **Agent Release** | Immutable snapshot of an Agent used for released execution. |
| **Agent Network** | First-class composition of Agents. A Project may own multiple Networks. |
| **Network Release** | Immutable snapshot of a Network and its versioned Agent bindings. |
| **Session** | Long-lived conversational context across executions. |
| **Agent Run** | One finite logical Agent execution. |
| **Network Run** | One finite Network execution coordinating causally related Agent Runs. |
| **Trace** | Observable evidence of what happened during execution. |
| **Collection** | Operational aggregate for Project Knowledge/RAG content. |
| **Document** | Source material uploaded into a Collection. |
| **Vector Snapshot** | Versioned representation of the exact knowledge state and indexing parameters. |
| **Tool** | External Agent capability exposed through HTTP or MCP. |
| **ChatSurface** | Browser-facing conversational surface bound to a released Agent or Network. |

## Core capabilities

- **Agent lifecycle** — controlled configuration, versioning, staging, immutable releases and rollback.
- **Agent Networks** — versioned multi-Agent composition with independent releases, Runs, Sessions and Traces.
- **Runtime API** — synchronous, streaming and asynchronous execution without creating separate execution ontologies.
- **Observability** — Runs, Traces, execution events, usage metadata and release provenance.
- **Knowledge / RAG** — Collections, Documents, ingestion, chunks and Vector Snapshots.
- **Tools** — HTTP and MCP capabilities with server-side credentials and execution policy.
- **Provider configuration** — reusable provider/model configuration with credentials kept server-side.
- **ChatSurface** — separately deployable browser runtime for published conversational experiences.
- **Environment semantics** — mutable Development/Draft, validation in Staging and immutable Production releases.
- **Project isolation** — technical resources and runtime state are scoped to a Project under an Organization.

## Repository architecture

The repository is organized by **product**, **engineering tooling** and **cross-system validation**.

```text
woobe/
├── packages/                 # product / distributable artifacts
│   ├── woobe-core/
│   ├── woobe-api/
│   ├── woobe-workers/
│   ├── woobe-frontend/
│   ├── woobe-embed/
│   └── woobe-ee/
│
├── tooling/                  # engineering and development tooling
│   ├── woobe-testkit/
│   ├── woobe-mock/
│   └── quality-gate/
│
├── tests/                    # repository and cross-system validation
│   ├── architecture/
│   ├── contract/
│   ├── integration/
│   ├── security/
│   └── e2e/
│
├── scripts/                  # operational, maintenance and CI scripts
├── docs/                     # architecture, operations and product documentation
├── docker/                   # Docker-specific validation/support assets
├── deploy/                   # optional deployment overlays, including contributor development
├── .github/                  # GitHub workflows and repository automation
│
├── compose.yaml              # supported Community self-host topology
├── compose.test.yaml         # standalone backend validation topology
├── pyproject.toml            # root Python dependency/tooling manifest
└── README.md
```

Each root directory contains its own `README.md` describing its ownership and expected contents.

### Product packages

`packages/` contains only product or explicit distributable boundaries.

| Package | Responsibility |
| --- | --- |
| `woobe-core` | Community/Core bounded contexts, application/runtime contracts, shared infrastructure, module-local presentation/composition and Alembic migrations. |
| `woobe-api` | HTTP process composition root: FastAPI bootstrap, middleware, transport registration and public API entrypoints. |
| `woobe-workers` | Worker process composition root. Concrete workers remain with the bounded context that owns them in Core. |
| `woobe-frontend` | Administrative control-plane frontend. |
| `woobe-embed` | Independently built and deployable ChatSurface browser artifact. |
| `woobe-ee` | Reserved public boundary for separately licensed Enterprise capabilities. |

Dependency direction is intentional:

```text
woobe-api ───────► woobe-core
woobe-workers ───► woobe-core
woobe-ee ────────► woobe-core   # when Enterprise implementation exists

woobe-core ──X──► woobe-api
woobe-core ──X──► woobe-workers
woobe-core ──X──► tooling
packages/* ──X──► tooling/*
```

Frontend and Embed communicate through HTTP/browser contracts rather than importing backend internals.

### Engineering tooling

`tooling/` contains development-only packages used to build and validate Woobe:

- `woobe-testkit` — shared test helpers.
- `woobe-mock` — protocol mocks and fault-injection helpers.
- `quality-gate` — executable architecture checker, policies and responsibility contracts.

Tooling may consume product packages for validation. Product runtime code must never depend on tooling.

### Cross-system tests

`tests/` contains validation that spans package, repository or assembled-system boundaries. End-to-end validation lives in `tests/e2e` because it validates the product; it is not itself a production package.

Detailed repository boundaries are documented in `docs/ARCHITECTURE.md` and `docs/adr/0004-package-workspace-and-process-boundaries.md`.

## Runtime and releases

Woobe separates mutable configuration from released execution.

- Development/Draft is editable.
- Staging is used to validate a candidate configuration.
- Production must execute immutable Agent Releases and Network Releases.
- Rollback reactivates a previous immutable Release instead of rebuilding historical state.
- Runs and Traces preserve the versions and runtime provenance used by an execution.

A Project may contain multiple Agent Networks. Network versioning is independent from Agent versioning, so composition itself is treated as a production artifact.

## Knowledge / RAG

Knowledge is Project-scoped and organized around Collections. Documents belong to Collections. Ingestion produces chunks and vectorized representations that can be bound to Agents.

Vector Snapshots identify the exact knowledge state and indexing parameters used by a runtime configuration, making knowledge provenance explicit instead of treating a live mutable index as an invisible dependency.

## Tools and providers

Woobe's external Tool boundaries are **HTTP** and **MCP**. Credentials remain server-side and critical authorization belongs to the backend.

Model/provider configuration is also controlled independently from product code so released Agents can preserve the exact configuration used at runtime.

## ChatSurface

ChatSurface is the browser-facing conversational surface for released Woobe products. It is a separate product artifact under `packages/woobe-embed` and can be built and deployed independently from the administrative frontend.

The browser should not receive permanent server-side ChatSurface credentials. Durable authorization and Session ownership remain server-side.

See `docs/runtime/CHAT_SURFACE.md`.

## Quick start

The supported Community self-host topology is the root `compose.yaml`.

Requirements:

- Docker with Docker Compose
- Python 3 for first-run environment generation

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

Default local endpoints:

```text
Web UI:      http://localhost:8080
API:         http://localhost:8000
ChatSurface: http://localhost:8081
```

For public exposure, secrets, TLS, backup, restore and upgrade requirements, read `docs/SELF_HOSTING.md`.

## Community runtime topology

| Service | Responsibility | Default exposure |
| --- | --- | --- |
| **PostgreSQL + pgvector** | Durable application state and vector-capable persistence | Internal |
| **RabbitMQ** | Asynchronous runtime and background work | Internal |
| **Redis** | Shared runtime coordination and ephemeral distributed state | Internal |
| **Migrations** | Applies the Core-owned database schema before API startup | One-shot |
| **API** | Control-plane and runtime HTTP surface | `:8000` |
| **Workers** | Background and asynchronous execution | Internal |
| **Web** | Administrative Woobe control plane | `:8080` |
| **ChatSurface** | Browser-facing conversational runtime assets | `:8081` |

Alembic configuration and migration history are currently owned by `packages/woobe-core`. A separate database package is intentionally not part of the current repository architecture.

## Security model

Critical rules are backend responsibilities, including authorization, ownership, Release immutability, runtime scopes, credential handling, Project isolation and operational state transitions.

The frontend reflects those rules but is not the security boundary.

Read `SECURITY.md` before operating a public installation.

## Distribution model

Woobe is **source-available and self-hostable**. It is not represented as OSI Open Source software.

The public repository contains the Community/Core product boundary. Proprietary managed Cloud implementation is not distributed here. `packages/woobe-ee` reserves the Enterprise package boundary without making Community depend on proprietary runtime code.

```text
Community  = distributed Core / self-hostable product
Cloud      = Woobe-managed product; proprietary implementation is not distributed here
Enterprise = separately licensed capabilities behind the reserved EE boundary
```

See `LICENSE.md`, `LICENSING.md`, `NOTICE.md` and `TRADEMARKS.md` for the current distribution terms and notices.

## Contributing

The integration branch is `master`.

Feature and fix branches should start from `master` and target `master` through focused pull requests. Do not mix unrelated refactors into feature changes.

Read `CONTRIBUTING.md` before opening a change.

## Documentation

Start with:

- `docs/ARCHITECTURE.md` — product and repository boundaries.
- `docs/SELF_HOSTING.md` — supported self-host operation.
- `docs/UPGRADING.md` — upgrade requirements.
- `docs/runtime/` — runtime-specific documentation.
- `docs/adr/` — durable architectural decisions.
- `docs/PUBLIC_RELEASE_CHECKLIST.md` — remaining public-release gates.

## License

Woobe Community/Core is distributed under the source-available terms in `LICENSE.md`. The current license text remains pre-release and should receive qualified legal review before public or commercial reliance.
