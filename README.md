# Woobe

### Control plane for building, releasing, and operating AI products.

Woobe is an **API-first, self-hostable platform for teams running AI agents and agent networks in production**. It connects configuration, versioning, releases, runtime, observability, knowledge, tools, and embedded chat under one operational model.

The core principle is simple: **production should run immutable, traceable releases — not mutable drafts**.

> **Pre-release status**
>
> Woobe is being prepared for its first public Community release. Public interfaces, deployment contracts, and the Community license remain pre-release until the release checklist is completed.

## Why Woobe

Building an agent is only one part of operating an AI product. Production teams also need to know which prompt ran, which model configuration was active, which tools and knowledge were bound, which network version coordinated an execution, what happened during the run, and how to restore a previous working state.

```text
Configure
   ↓
Draft
   ↓
Validate in Staging
   ↓
Create immutable Release
   ↓
Deploy to Production
   ↓
Run · Trace · Observe
   ↓
Rollback when needed
```

## Key capabilities

- **Agents** — prompts, model settings, tools, knowledge, runtime behavior, and structured output contracts.
- **Agent Releases** — immutable snapshots for production execution.
- **Agent Networks** — coordinated multi-agent behavior versioned independently from individual Agents.
- **Network Releases** — immutable snapshots of network composition and versioned bindings.
- **Environments** — explicit Draft/Development, Staging, and Production semantics.
- **Rollback** — restore an existing immutable release instead of rebuilding old configuration.
- **Runtime API** — synchronous execution, streaming, and asynchronous jobs under the same Run semantics.
- **Sessions and Runs** — long-lived conversational context separated from finite executions.
- **Tracing and observability** — execution events, metadata, usage, and exact versions involved in each Run.
- **Knowledge / RAG** — Collections, Documents, chunks, ingestion state, and Vector Snapshots.
- **HTTP and MCP Tools** — external capabilities with credentials and execution policy kept server-side.
- **BYOK providers** — use your own model-provider credentials.
- **ChatSurface** — embed released Agents or Networks using server-side Access Keys and short-lived browser tokens.
- **Metering** — operational usage accounting kept separate from managed-service billing.
- **Workspaces and Projects** — commercial membership separated from technical isolation.

## Core concepts

| Concept | Responsibility |
| --- | --- |
| **Workspace** | Commercial and membership boundary. Owns members and Projects. |
| **Project** | Technical isolation boundary for Agents, Networks, Tools, Knowledge, runtime, Runs, and Traces. |
| **Agent** | Mutable AI configuration during development. |
| **Agent Release** | Immutable Agent snapshot consumed by Production. |
| **Agent Network** | First-class operational composition of Agents inside a Project. A Project may own multiple Networks. |
| **Network Release** | Immutable snapshot of a Network and its versioned bindings. |
| **Session** | Long-lived conversational context. |
| **Agent Run** | One finite logical Agent execution. |
| **Network Run** | One finite Network execution coordinating related Agent Runs. |
| **Trace** | Observable evidence of what happened during a Run. |
| **Collection** | Operational aggregate for Knowledge/RAG content. |
| **Document** | Source material uploaded into a Collection. |
| **Vector Snapshot** | Versioned representation of the exact knowledge state and indexing parameters. |
| **Tool** | External capability exposed to an Agent through HTTP or MCP. |
| **ChatSurface** | Embeddable browser runtime for released Agents and Networks. |

## Quick start

Woobe Community has one supported default self-host contract: the root `compose.yaml`.

Requirements:

- Docker with Docker Compose
- Python 3 for first-run environment generation

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

Open:

```text
Web UI:     http://localhost:8080
API:        http://localhost:8000
Chat Embed: http://localhost:8081
```

The first registration on a fresh Community database bootstraps the instance and creates the first Instance Owner and initial Workspace. After bootstrap, Community defaults to invite-only registration.

For public exposure, backup, restore, TLS, and upgrade requirements, read `docs/SELF_HOSTING.md`.

## Community topology

The default topology is intentionally small and single-host oriented.

| Service | Purpose | Default exposure |
| --- | --- | --- |
| **PostgreSQL + pgvector** | Durable application state and vector-capable persistence | Internal |
| **RabbitMQ** | Asynchronous runtime and background work | Internal |
| **Redis** | Shared runtime coordination and ephemeral distributed state | Internal |
| **Migrations** | Applies the database schema before API startup | One-shot |
| **API** | Control-plane and runtime HTTP surface | `:8000` |
| **Workers** | Background and asynchronous execution | Internal |
| **Web** | Woobe control-plane interface | `:8080` |
| **Chat Embed** | Browser-facing ChatSurface assets | `:8081` |

PostgreSQL, RabbitMQ, Redis, and local Knowledge uploads are composed by the supported Community deployment. Contributor-only infrastructure is layered explicitly through `deploy/dev/compose.yml`.

## From development to production

Draft configuration is mutable. Staging validates configuration intended for release. Production runs immutable Agent Releases and Network Releases. Rollback restores an earlier immutable release rather than reconstructing old state.

A self-hosted Community instance uses the same root `compose.yaml` with `WOOBE_ENVIRONMENT=production` plus production-safe secrets, cookies, host allowlists, TLS termination, and backup procedures.

## Agent Networks

A Project may own multiple Agent Networks. Each Network is a first-class operational entity with its own composition, versions, releases, runs, sessions, traces, and configuration. Network versioning is independent from Agent versioning so composition itself is a production artifact.

In Production, Networks bind to released Agents so mutable Agent configuration cannot silently change production behavior.

## Knowledge and RAG

Knowledge is Project-scoped and organized around Collections. Documents belong to Collections; ingestion produces chunks and vectorized representations that can be bound to Agents. Vector Snapshots identify the exact knowledge state and indexing parameters associated with runtime configuration.

## Tools and model providers

Woobe focuses on two external Tool boundaries: HTTP Tools and MCP Tools. Provider credentials, Tool credentials, Runtime Keys, and other sensitive values remain server-side. Self-hosted deployments use their own provider accounts under a BYOK model.

## ChatSurface

ChatSurface is Woobe's embeddable runtime surface for released AI products. A ChatSurface targets an immutable Agent Release or Network Release. The integrating application keeps the durable relationship between its own user and the Woobe Session, while Woobe remains responsible for conversation history and execution metadata.

The browser never receives the permanent server-side ChatSurface Access Key. The integrator exchanges it server-side for short-lived Session access suitable for browser use.

See `docs/runtime/CHAT_SURFACE.md`.

## API-first runtime

The Web UI is a client of the same backend domain rules that protect the runtime. Critical behavior belongs to the backend, including ownership checks, authorization, Release immutability, runtime scopes, document duplicate rules, signup policy, and credential security.

Runtime delivery can be synchronous, streaming, or asynchronous without creating separate execution models.

## Distribution model

This repository and the supported self-host artifacts distribute **Woobe Community/Core only**.

```text
Community  = Core distributed here
Cloud      = proprietary Woobe-managed product; implementation is not distributed here
Enterprise = reserved product boundary; no proprietary runtime implementation is distributed here
```

Community does not require a Woobe Cloud account, has no required call-home dependency, and does not add a Woobe per-Run fee. The operator owns its infrastructure, model-provider costs, and external services used through Tools.

Woobe Cloud may build on the same core concepts, but proprietary Cloud implementation is intentionally outside the Community source tree and Community container build context. `packages/woobe-ee` is a reserved public package boundary only and contains no Enterprise runtime implementation in the Community distribution.

## Repository architecture

The repository separates product artifacts from engineering tooling and assembled-system validation:

```text
packages/                         # product / distributable artifacts
├── woobe-core/                   # bounded contexts + shared Community/Core code + migrations
├── woobe-api/                    # HTTP process composition root
├── woobe-workers/                # worker process composition root
├── woobe-frontend/               # administrative control-plane frontend
├── woobe-embed/                  # independently deployable ChatSurface embed
└── woobe-ee/                     # reserved Enterprise boundary

tooling/                          # engineering/development only
├── woobe-testkit/                # shared test helpers
├── woobe-mock/                   # protocol mocks/fault injection
└── quality-gate/                 # architecture checker and policies

tests/                            # repository/cross-system validation
├── architecture/
├── contract/
├── integration/
├── security/
└── e2e/
```

`woobe-core` contains the bounded contexts, their module-local presentation/composition code, and the current Alembic configuration/history at `packages/woobe-core/alembic.ini` and `packages/woobe-core/migrations/`. `woobe-api` owns process-level FastAPI composition; `woobe-workers` owns the worker process composition root. API and Workers may depend on Core. Core must not depend on API, Workers, or Enterprise implementation.

`packages/woobe-frontend` and `packages/woobe-embed` are separate product artifacts: the first is the control-plane UI; the second is the browser-facing ChatSurface runtime. Engineering packages under `tooling/` may depend on product packages for validation, but production packages must never depend on tooling. E2E belongs to `tests/e2e` because it validates the assembled system rather than constituting a product package.

A separate database package is intentionally outside this repository cutover and may be introduced by a dedicated future PR.

Read `docs/ARCHITECTURE.md` and `docs/adr/0004-package-workspace-and-process-boundaries.md` for the detailed boundaries.

## Deployment surface

```text
compose.yaml                 # supported Community self-host topology
compose.test.yaml            # standalone backend validation contract
deploy/dev/compose.yml       # optional contributor extension
```

Default user path:

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

Backend validation path:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

## Security model

Woobe requires strong independent application and encryption secrets, secure cookies in Production, explicit CORS and Trusted Host allowlists, server-side provider and Tool credentials, short-lived ChatSurface browser access, immutable Production Release bindings, and backend ownership enforcement.

Read `SECURITY.md` before operating a public installation.

## Backup and upgrades

Back up PostgreSQL together with the Knowledge upload volume so metadata and physical files remain consistent.

- `docs/SELF_HOSTING.md`
- `docs/UPGRADING.md`
- `docs/runbooks/postgres-backup-restore.md`
- `docs/runbooks/production-deployment.md`

## Contributing

The integration branch is `master`. Feature and fix branches should start from `master` and target `master` through focused pull requests. Read `CONTRIBUTING.md` before opening a change.

External contribution acceptance remains gated by the contribution policy described in `CONTRIBUTOR_LICENSE_AGREEMENT.md` until the final process is activated.

## License

Woobe Community/Core is distributed as **source-available, fair-code, and self-hostable software** under `LICENSE.md`. It is not represented as OSI Open Source software.

`LICENSING.md` explains the intended Community/Cloud/Enterprise product boundary. `TRADEMARKS.md` and `NOTICE.md` contain additional public-distribution notices.

The current Community license text is a pre-release candidate and must receive qualified legal review before public or commercial reliance. The public release also remains blocked on repository-history review and completion of third-party dependency notices as described in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
