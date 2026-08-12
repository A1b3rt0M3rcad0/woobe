# Woobe

### Control plane for building, releasing, and operating AI products.

Woobe is an **API-first, self-hostable platform for teams running AI agents and agent networks in production**. It connects configuration, versioning, releases, runtime, observability, knowledge, tools, and embedded chat under one operational model.

The core principle is simple: **production should run immutable, traceable releases — not mutable drafts**.

[Quick Start](#quick-start) · [Capabilities](#key-capabilities) · [Architecture](#architecture) · [Self-hosting](docs/SELF_HOSTING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [License](#license)

> **Pre-release status**
>
> Woobe is being prepared for its first public Community release. Public interfaces, deployment contracts, and license documents remain pre-release until that release is finalized.

---

## Why Woobe

Building an agent is only one part of operating an AI product.

Production teams also need to know which prompt ran, which model configuration was active, which tools and knowledge were bound, which network version coordinated an execution, what happened during the run, and how to restore a previous working state without reconstructing configuration manually.

Woobe treats those concerns as one lifecycle:

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

Runs and Traces retain the versions and runtime bindings that were actually used, keeping configuration and execution connected throughout the product lifecycle.

## Key capabilities

- **Agents** — prompts, model settings, tools, knowledge, runtime behavior, and structured output contracts.
- **Agent Releases** — immutable snapshots for production execution.
- **Agent Networks** — coordinated multi-agent behavior versioned independently from individual Agents.
- **Network Releases** — immutable snapshots of network composition and versioned bindings.
- **Environments** — explicit Draft/Development, Staging, and Production semantics.
- **Rollback** — restore an existing immutable release instead of rebuilding an old configuration.
- **Runtime API** — synchronous execution, streaming, and asynchronous jobs under the same Run semantics.
- **Sessions and Runs** — long-lived conversational context separated from finite executions.
- **Tracing and observability** — execution events, metadata, usage, and exact versions involved in each Run.
- **Knowledge / RAG** — Collections, Documents, chunks, ingestion state, and Vector Snapshots.
- **HTTP and MCP Tools** — external capabilities with credentials and execution policy kept server-side.
- **BYOK providers** — use your own model-provider credentials.
- **ChatSurface** — embed released Agents or Networks using server-side Access Keys and short-lived browser tokens.
- **Metering** — operational usage accounting kept separate from Cloud billing.
- **Organizations and Projects** — commercial membership separated from technical isolation.

## Core concepts

| Concept | Responsibility |
| --- | --- |
| **Organization** | Commercial and membership boundary. Owns members and Projects. |
| **Project** | Technical isolation boundary for Agents, Networks, Tools, Knowledge, runtime, Runs, and Traces. |
| **Agent** | Mutable AI configuration during development. |
| **Agent Release** | Immutable Agent snapshot consumed by Production. |
| **Agent Network** | Operational composition of Agents inside a Project. |
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

Woobe Community has one supported default self-host contract: the root [`compose.yaml`](compose.yaml).

### Requirements

- Docker with Docker Compose
- Python 3 for first-run environment generation

### Start Woobe Community

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

The first registration on a fresh Community database atomically bootstraps the instance, creates the first **Instance Owner**, creates the initial **Organization**, assigns its owner membership, and starts the authentication session.

After bootstrap, Community defaults to **invite-only registration**. Arbitrary public registration is rejected by the backend.

For public exposure, backup, restore, TLS, and upgrade requirements, read [Self-hosting Woobe Community](docs/SELF_HOSTING.md).

## Community topology

The default topology is intentionally small and single-host oriented.

| Service | Purpose | Default exposure |
| --- | --- | --- |
| **PostgreSQL + pgvector** | Durable application state and vector-capable persistence | Internal |
| **RabbitMQ** | Asynchronous runtime and background work | Internal |
| **Migrations** | Applies the database schema before API startup | One-shot |
| **API** | Control-plane and runtime HTTP surface | `:8000` |
| **Workers** | Background and asynchronous execution | Internal |
| **Web** | Woobe control-plane interface | `:8080` |
| **Chat Embed** | Browser-facing ChatSurface assets | `:8081` |

PostgreSQL, RabbitMQ, and local Knowledge uploads use the persistent Docker volumes `woobe_postgres`, `woobe_rabbitmq`, and `woobe_uploads`.

Redis, PgBouncer, and MinIO are **not part of the default Community product topology**. Contributors who need to exercise those integrations locally can explicitly layer [`deploy/dev/compose.yml`](deploy/dev/compose.yml):

```bash
docker compose -f compose.yaml -f deploy/dev/compose.yml up -d --build
```

That file is a contributor topology, not a second supported self-host distribution.

## From development to production

Woobe separates product environment semantics from infrastructure topology.

### Draft / Development

Draft configuration is mutable. Prompts, model configuration, tools, knowledge bindings, output contracts, runtime settings, and Network composition are edited here.

### Staging

Staging validates the configuration intended for release before Production promotion.

### Production

Production runs immutable Agent Releases and Network Releases. A Release preserves the configuration snapshot required to reproduce what was deployed, and rollback can restore an earlier release without rebuilding it.

For a self-hosted Community instance, Production is **not a different Compose product**. The same root `compose.yaml` is operated with `WOOBE_ENVIRONMENT=production` and production-safe secrets, cookies, host allowlists, TLS termination, and backup procedures.

Woobe does not currently advertise a separate distributed/external-infrastructure Compose topology as part of the Community MVP support surface.

## Agent Networks

Woobe starts with a single Agent and grows into an Agent Network when coordinated behavior is required.

A Project owns one operational Agent Network. The Network is versioned independently from its Agents so the composition itself is a first-class production artifact.

In Staging, a Network can validate staging or released Agent versions according to runtime policy. In Production, the Network must bind to released Agents so mutable configuration cannot silently change production behavior.

## Knowledge and RAG

Knowledge is Project-scoped and organized around **Collections**. Documents belong to Collections; ingestion produces chunks and vectorized representations that can be bound to Agents.

**Vector Snapshots** identify the exact combination of Collections, Documents, and indexing parameters associated with runtime configuration. The goal is not only retrieval, but knowing **which knowledge state was used by a specific execution**.

Community persists uploaded files locally by default. S3-compatible storage can be exercised by contributors through the optional development topology, but a distributed deployment contract is not part of the current Community MVP support surface.

## Tools and model providers

Woobe currently focuses on two external Tool boundaries:

- **HTTP Tools** for external HTTP APIs.
- **MCP Tools** for Model Context Protocol servers.

Provider credentials, Tool credentials, Runtime Keys, and other sensitive values remain server-side. Self-hosted deployments use their own provider accounts under a BYOK model.

See [MCP Tools](docs/runtime/MCP_TOOLS.md) for the current MCP runtime contract.

## ChatSurface

ChatSurface is Woobe's embeddable runtime surface for released AI products.

A ChatSurface targets an immutable Agent Release or Network Release. The integrating application keeps the durable relationship between its own user and the Woobe Session, while Woobe remains responsible for conversation history and execution metadata.

The browser never receives the permanent server-side ChatSurface Access Key. The integrator exchanges it server-side for short-lived Session access suitable for browser use.

See [ChatSurface](docs/runtime/CHAT_SURFACE.md) for the integration and security contract.

## API-first runtime

The Web UI is a client of the same backend domain rules that protect the runtime. Critical behavior belongs to the backend, including ownership checks, authorization, Release immutability, runtime scopes, document duplicate rules, signup policy, and edition boundaries.

Runtime delivery can be synchronous, streaming, or asynchronous without creating separate execution models. See [Streaming](docs/runtime/STREAMING.md) for the current streaming contract.

## Editions

Woobe uses **composition, not forks**, to separate product editions.

```text
Community = Core
Cloud     = Core + Cloud modules
Enterprise = Core + Enterprise modules (when introduced)
```

### Woobe Community

`WOOBE_EDITION=community` runs the shared self-hosted core. Community does not require a Woobe Cloud account, has no required call-home dependency, and does not add a Woobe per-Run fee. The operator owns its infrastructure, model-provider costs, and external services used through Tools.

### Woobe Cloud

`WOOBE_EDITION=cloud` composes Cloud-specific capabilities on top of the same shared core. Billing is currently the Cloud-specific bounded context present in this repository.

```text
src/editions/cloud/**
web/src/editions/cloud/**
```

The Community/Core runtime does not import or mount Cloud functionality when running as Community.

## Architecture

```text
src/
├── modules/                       # Community/Core
│   ├── identity/
│   ├── core/
│   ├── agent/
│   ├── network/
│   ├── chat_surface/
│   ├── metering/
│   └── observability/
├── editions/
│   └── cloud/
│       └── billing/
└── shared/

web/
├── src/features/                  # Community/Core UI
└── src/editions/cloud/            # Cloud-only UI
```

At runtime, API and Workers are separate processes. PostgreSQL stores durable state, RabbitMQ carries asynchronous work, Web serves the control plane, and Chat Embed publishes the browser-facing ChatSurface assets.

The backend remains the source of truth for domain invariants. The frontend reflects those rules but is never their only enforcement layer.

Read [Architecture](docs/ARCHITECTURE.md) for domain, runtime, and edition boundaries.

## Deployment surface

Woobe keeps product deployment, validation, and contributor infrastructure as separate contracts:

```text
compose.yaml                 # supported Community self-host topology
compose.test.yaml            # standalone validation contract
deploy/dev/compose.yml       # optional contributor extension
```

The default user path is always:

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

The validation path is explicitly selected and does not change the default Community distribution:

```bash
docker compose -f compose.test.yaml run --rm tests
```

Do not treat `compose.test.yaml` or `deploy/dev/compose.yml` as production distributions. `compose.test.yaml` is isolated test infrastructure; `deploy/dev/compose.yml` is an optional contributor extension. Additional production deployment topologies should only become public contracts when Woobe is prepared to support them operationally.

## Configuration

Application configuration uses the `WOOBE_` prefix. Frontend build-time public configuration uses `VITE_*`.

Generate a fresh Community environment with:

```bash
python scripts/generate_self_host_env.py
```

The generator writes `.env` with independent random application, encryption, ChatSurface, PostgreSQL, and RabbitMQ secrets. Do not copy development credentials into a public deployment.

## Security model

Production AI infrastructure needs explicit backend and runtime boundaries.

Woobe requires or documents, among other controls:

- strong, distinct authentication, encryption, and ChatSurface signing secrets;
- secure authentication cookies in Production;
- explicit CORS and Trusted Host allowlists;
- server-side provider and Tool credentials;
- no permanent ChatSurface Access Key exposure to browsers;
- immutable Release bindings for Production execution;
- backend ownership and authorization enforcement.

Read [SECURITY.md](SECURITY.md) before reporting a vulnerability or operating a public installation.

## Backup and upgrades

Self-hosting requires a recovery path. Back up PostgreSQL together with the Knowledge upload volume so metadata and physical files remain consistent.

- [Self-hosting](docs/SELF_HOSTING.md)
- [Upgrading](docs/UPGRADING.md)
- [PostgreSQL backup and restore](docs/runbooks/postgres-backup-restore.md)
- [Production deployment](docs/runbooks/production-deployment.md)

## Documentation

| Document | Purpose |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Domain, runtime, and edition boundaries. |
| [Self-hosting](docs/SELF_HOSTING.md) | Community installation and production exposure. |
| [Upgrading](docs/UPGRADING.md) | Version upgrade procedure. |
| [ChatSurface](docs/runtime/CHAT_SURFACE.md) | Embed, Session, token, Release, and security contract. |
| [MCP Tools](docs/runtime/MCP_TOOLS.md) | MCP lifecycle, OAuth, permissions, and security. |
| [Streaming](docs/runtime/STREAMING.md) | Runtime streaming protocol. |
| [Compose tests](docs/testing/COMPOSE_TESTS.md) | Standalone local/CI validation topology and commands. |
| [Provider contributions](docs/CONTRIBUTING_PROVIDERS.md) | Provider contribution guidance. |
| [Security](SECURITY.md) | Vulnerability reporting and security expectations. |
| [Contributing](CONTRIBUTING.md) | Development and contribution workflow. |
| [Changelog](CHANGELOG.md) | Release-oriented project history. |

## Contributing

The integration branch is `development`. Feature and fix branches should target `development` through focused pull requests.

The public repository is the product repository, not an archive of internal implementation plans or development tooling. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change.

## License

Woobe Community/Core is distributed as **source-available, fair-code, and self-hostable software** under [LICENSE.md](LICENSE.md). It is not represented as OSI Open Source software.

Code under `src/editions/**` and `web/src/editions/**` is outside the automatic scope of the Community/Core license. Cloud edition code currently present in those paths is governed by [LICENSE-CLOUD.md](LICENSE-CLOUD.md).

The current license texts are pre-release candidates and must receive qualified legal review before public/commercial reliance.

See [COMMERCIAL-LICENSE.md](COMMERCIAL-LICENSE.md), [TRADEMARKS.md](TRADEMARKS.md), and [NOTICE.md](NOTICE.md) for additional terms and notices.
