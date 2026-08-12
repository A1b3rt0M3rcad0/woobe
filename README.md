# Woobe

### Control plane for building, releasing, and operating AI products.

Woobe is an **API-first, self-hostable platform for teams running AI agents and agent networks in production**. It brings configuration, versioning, releases, runtime, observability, knowledge, tools, and embedded chat under one operational model.

The core idea is simple: **production should run immutable, traceable releases — not mutable drafts**.

Woobe gives teams a controlled path from the first working agent to a versioned AI product that can be staged, published, observed, and rolled back without losing the exact configuration that produced each execution.

[Quick Start](#quick-start) · [Key Capabilities](#key-capabilities) · [Core Concepts](#core-concepts) · [Architecture](#architecture) · [Self-hosting](docs/SELF_HOSTING.md) · [Security](SECURITY.md) · [Contributing](CONTRIBUTING.md) · [License](#license)

> **Pre-release status**
>
> Woobe is being prepared for its first public Community release. Public interfaces, deployment contracts, and license documents should be treated as pre-release until that release is finalized.

---

## Why Woobe

Building an agent is only one part of running an AI product.

Once an agent reaches production, teams also need to know which prompt ran, which model configuration was active, which tools and knowledge were bound, which network version coordinated the execution, what happened during the run, and how to restore the previous working state when a release fails.

Woobe treats those concerns as part of the product lifecycle rather than as unrelated infrastructure.

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

Configuration and runtime stay connected throughout the lifecycle. Runs and Traces retain the versions and runtime bindings that were actually used, making production behavior reproducible and inspectable.

## Key capabilities

- **Agents** — configure prompts, model settings, tools, knowledge, runtime behavior, and structured output contracts.
- **Agent Releases** — publish immutable snapshots instead of running production directly from mutable drafts.
- **Agent Networks** — compose the operational behavior of multiple agents inside a Project and version that composition independently.
- **Network Releases** — publish immutable network snapshots with controlled agent bindings.
- **Environments** — move changes through Draft/Development, Staging, and Production with explicit release semantics.
- **Rollback** — restore a previous immutable release instead of reconstructing old configuration manually.
- **Runtime API** — execute AI products through synchronous requests, streaming responses, and asynchronous jobs.
- **Runs and Sessions** — separate finite execution occurrences from long-lived conversational context.
- **Tracing and observability** — inspect Agent Runs, Network Runs, events, execution metadata, and the versions involved in each execution.
- **Knowledge / RAG** — manage Collections, Documents, chunks, ingestion state, and Vector Snapshots that identify the exact knowledge set used by runtime bindings.
- **Tools** — connect agents to HTTP and MCP tools while keeping execution policy and credentials server-side.
- **Provider credentials / BYOK** — operate with your own model-provider credentials.
- **ChatSurface** — publish an Agent Release or Network Release into web applications using server-side Access Keys and short-lived browser session tokens.
- **Usage and Metering** — record operational usage independently from Cloud billing concerns.
- **Organizations and Projects** — separate commercial membership from technical isolation.

## Core concepts

| Concept | Responsibility |
| --- | --- |
| **Organization** | Commercial and membership boundary. Owns members and Projects. |
| **Project** | Technical isolation boundary. Agents, Networks, Tools, Knowledge, Runtime Keys, Runs, and Traces are Project-scoped. |
| **Agent** | Mutable AI configuration during development. |
| **Agent Release** | Immutable snapshot of an Agent configuration. Production consumes releases, not mutable drafts. |
| **Agent Network** | The operational composition of agents inside a Project. A Project has one operational Agent Network. |
| **Network Release** | Immutable snapshot of the network and its versioned bindings. |
| **Session** | Long-lived conversational context associated with runtime usage. |
| **Agent Run** | One finite logical execution of an Agent. |
| **Network Run** | One finite network execution coordinating causally related Agent Runs. |
| **Trace** | Observable evidence of what happened during a Run. |
| **Collection** | Operational aggregate for Knowledge/RAG content. |
| **Document** | Source material uploaded into a Collection. |
| **Vector Snapshot** | Versioned representation of the exact knowledge set and indexing parameters available to runtime. |
| **Tool** | External capability available to an Agent through HTTP or MCP. |
| **ChatSurface** | Embeddable web runtime for released Agents and Networks. |

## Quick start

Woobe Community can run locally with Docker Compose.

### Requirements

- Docker with Docker Compose
- Python 3 for initial environment generation

### Start Woobe Community

From a fresh checkout:

```bash
python scripts/generate_self_host_env.py
docker compose -f docker-compose.community.yml up -d --build
```

Open:

```text
Web UI:     http://localhost:8080
API:        http://localhost:8000
Chat Embed: http://localhost:8081
```

The first registration on a fresh Community database performs the instance bootstrap atomically and creates the first **Instance Owner**, the initial **Organization**, its owner membership, and the authentication session.

After bootstrap, Community defaults to **invite-only registration**. Arbitrary public registration is rejected by the backend.

For production exposure, persistent storage, backup, restore, TLS, and upgrade guidance, read [Self-hosting Woobe Community](docs/SELF_HOSTING.md).

## What the Community stack starts

The default Community topology is intentionally small enough to run on a single host while preserving the same application boundaries used by larger deployments.

| Service | Purpose | Default exposure |
| --- | --- | --- |
| **PostgreSQL + pgvector** | Durable application state and vector-capable persistence | Internal |
| **RabbitMQ** | Asynchronous runtime and module work | Internal |
| **Migrations** | Applies the database schema before API startup | One-shot |
| **API** | Control-plane and runtime HTTP surface | `:8000` |
| **Workers** | Background and asynchronous execution | Internal |
| **Web** | Woobe control-plane interface | `:8080` |
| **Chat Embed** | Browser-facing ChatSurface runtime assets | `:8081` |

Knowledge uploads are persisted in the `woobe_uploads` Docker volume. PostgreSQL and RabbitMQ use `woobe_postgres` and `woobe_rabbitmq` respectively.

Redis, PgBouncer, MinIO/S3-compatible storage, and more distributed deployment layouts remain available when the deployment requires them; they are not mandatory for the small Community topology.

## From development to production

Woobe separates editable configuration from production execution.

### Draft / Development

Draft configuration is mutable. This is where prompts, model configuration, tools, knowledge bindings, output contracts, runtime configuration, and network composition are edited.

### Staging

Staging is the validation environment. It exists to test the configuration that is intended to become production state before publishing an immutable release.

### Production

Production runs immutable Agent Releases and Network Releases. A release preserves the configuration snapshot required to reproduce what was deployed, while rollback can restore a previous release without rebuilding it manually.

This model also gives observability a stable reference: a Trace can point to the versions that actually participated in execution instead of only showing whatever the current draft looks like.

## Agent Networks

Woobe starts with a single Agent and grows into an Agent Network when the product needs coordinated behavior.

A Project owns one operational Agent Network. The network is versioned independently from its Agents so the composition itself is a first-class production artifact.

In Staging, a network can validate staging or released agent versions according to runtime policy. In Production, the network must bind to released Agents so a mutable Agent configuration cannot silently change a production network.

## Knowledge and RAG

Knowledge is Project-scoped and organized around **Collections**.

Documents belong to Collections, and ingestion produces chunks and vectorized representations that can be bound to Agents. Woobe uses **Vector Snapshots** to identify the exact combination of Collections, Documents, and indexing parameters associated with a runtime configuration.

The goal is not only retrieval. The goal is knowing **which knowledge state was used by a specific production execution**.

Community supports local persistent file storage by default and can use S3-compatible storage in more distributed deployments.

## Tools and model providers

Agents can use external capabilities without turning those integrations into frontend responsibilities.

Woobe currently focuses on two tool boundaries:

- **HTTP Tools** for external HTTP APIs.
- **MCP Tools** for Model Context Protocol servers.

Provider credentials, tool credentials, runtime keys, and other sensitive values remain server-side. Woobe supports a BYOK operating model so self-hosted deployments can use their own model-provider accounts.

## ChatSurface

ChatSurface is Woobe's embeddable runtime surface for released AI products.

A ChatSurface targets an immutable Agent Release or Network Release. The integrating application keeps the durable relationship between its own user and the Woobe Session, while Woobe remains responsible for the session's conversation history and execution metadata.

The browser does not receive the server-side ChatSurface Access Key. Instead, the integration exchanges server-side credentials for short-lived session access suitable for browser use.

This keeps the publication model consistent with the rest of Woobe: the user-facing chat runs a known release, and the resulting Sessions, Runs, and Traces remain attributable to that release.

## API-first runtime

The UI is a client of the same backend domain rules that protect the runtime.

Critical behavior belongs to the backend, including ownership checks, authorization, release immutability, runtime scopes, document duplicate rules, signup policy, and edition boundaries.

The runtime supports multiple delivery forms — synchronous HTTP, streaming, and asynchronous jobs — without treating them as different execution models. They all produce the same underlying Run and Trace semantics.

## Community and Cloud

Woobe uses **composition, not forks**, to separate product editions.

```text
Community = Core
Cloud     = Core + Cloud edition modules
```

### Woobe Community

`WOOBE_EDITION=community` runs the shared self-hosted core.

Community does not require a Woobe Cloud account, has no required call-home dependency, and does not add a Woobe per-Run fee. The operator is responsible for its own infrastructure, model providers, and external services used through Tools.

### Woobe Cloud

`WOOBE_EDITION=cloud` runs the same shared core and composes Cloud-specific capabilities on top of it. Billing is currently the Cloud-specific bounded context present in this repository.

Cloud functionality lives outside the Community/Core namespace:

```text
src/editions/cloud/**
web/src/editions/cloud/**
```

The shared core does not depend on Cloud modules when Woobe runs as Community.

See [Woobe Architecture](docs/ARCHITECTURE.md) for the edition boundary in detail.

## Architecture

Woobe is structured as a modular backend with explicit domain boundaries and process-separated runtime infrastructure.

```text
src/
├── modules/                       # Community/Core
│   ├── identity/                  # Users, Organizations, instance bootstrap
│   ├── core/                      # Projects and core technical boundaries
│   ├── agent/                     # Agents, releases, knowledge, tools, runtime
│   ├── network/                   # Agent Network and network runtime
│   ├── chat_surface/              # Embeddable released chat surface
│   ├── metering/                  # Operational usage accounting
│   └── observability/             # Traces and observability
│
├── editions/
│   └── cloud/
│       └── billing/               # Cloud-only bounded context
│
└── shared/                        # Cross-cutting infrastructure and contracts

web/
├── src/features/                  # Shared Community/Core UI
└── src/editions/cloud/            # Cloud-only UI
```

At runtime:

```text
                ┌───────────────────┐
                │       Web         │
                └─────────┬─────────┘
                          │
                          ▼
                ┌───────────────────┐
                │        API        │
                └──────┬─────┬──────┘
                       │     │
              durable │     │ async work
                       ▼     ▼
              ┌──────────┐  ┌──────────┐
              │PostgreSQL│  │ RabbitMQ │
              └──────────┘  └────┬─────┘
                                  │
                                  ▼
                           ┌─────────────┐
                           │   Workers   │
                           └─────────────┘

ChatSurface is exposed separately through the Chat Embed service while using the same released runtime model.
```

The backend remains the source of truth for domain rules. The frontend reflects those rules but is never the only enforcement layer.

For a deeper description of domain, runtime, and edition boundaries, read [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Deployment models

### Community / single-host

Use:

```bash
docker compose -f docker-compose.community.yml up -d --build
```

This topology includes the application and the minimum infrastructure required for a complete Community installation.

### Integrated development topology

`docker-compose.yml` includes the broader development stack, including PostgreSQL, PgBouncer, RabbitMQ, Redis, and MinIO.

### Production / external infrastructure

`docker-compose.prod.yml` is application-only. It is intended for deployments where PostgreSQL, RabbitMQ, cache, object storage, TLS termination, and related infrastructure are managed externally.

## Configuration

Application configuration uses the `WOOBE_` prefix.

Frontend build-time public configuration uses `VITE_*`.

A fresh Community environment can be generated with:

```bash
python scripts/generate_self_host_env.py
```

The generator creates independent random values for sensitive application configuration instead of shipping reusable production credentials.

Before exposing Woobe to the internet, review [docs/SELF_HOSTING.md](docs/SELF_HOSTING.md) and the production requirements in [.env.example](.env.example).

## Security model

Woobe assumes that production AI infrastructure needs explicit security boundaries rather than frontend-only controls.

Among the production requirements enforced or documented by the project:

- authentication and ChatSurface signing secrets must be strong and distinct;
- authentication cookies must be secure in production;
- CORS and Trusted Hosts use explicit allowlists;
- provider credentials and Runtime Keys stay server-side;
- ChatSurface server Access Keys are not exposed to browsers;
- production execution is pinned to immutable releases;
- critical ownership and authorization rules are enforced by the backend.

Please read [SECURITY.md](SECURITY.md) before reporting a security issue or operating a public installation.

## Backup and upgrades

Self-hosting is incomplete without a recovery path.

Woobe includes database backup and restore scripts and documents the persistence that must be backed up together with PostgreSQL.

- [Self-hosting](docs/SELF_HOSTING.md)
- [Upgrading](docs/UPGRADING.md)
- [PostgreSQL backup and restore](docs/runbooks/postgres-backup-restore.md)
- [Production deployment runbook](docs/runbooks/production-deployment.md)

If local Knowledge storage is enabled, back up the Knowledge upload volume together with the database so metadata and physical files remain consistent.

## Repository documentation

| Document | Purpose |
| --- | --- |
| [Architecture](docs/ARCHITECTURE.md) | Domain, runtime, and edition boundaries. |
| [Self-hosting](docs/SELF_HOSTING.md) | Community installation and production exposure. |
| [Upgrading](docs/UPGRADING.md) | Version upgrade procedure. |
| [Provider contributions](docs/CONTRIBUTING_PROVIDERS.md) | Provider contribution guidance. |
| [MCP Tools](docs/mcp-tools-mvp.md) | MCP tool behavior and integration notes. |
| [Security](SECURITY.md) | Vulnerability reporting and security expectations. |
| [Contributing](CONTRIBUTING.md) | Development and contribution workflow. |
| [Code of Conduct](CODE_OF_CONDUCT.md) | Community participation expectations. |
| [Changelog](CHANGELOG.md) | Release-oriented project history. |

## Contributing

Contributions should preserve the product's domain and edition boundaries instead of bypassing them for local convenience.

Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a change.

The integration branch is `development`. Feature and fix branches should target `development` through pull requests.

## License

Woobe Community/Core is distributed as **source-available, fair-code, and self-hostable software** under the terms in [LICENSE.md](LICENSE.md). It is not represented as OSI Open Source software.

The Community/Core license permits the uses described in that file, including internal business use and building products on top of Woobe, while restricting use cases such as offering the Woobe control plane itself as a hosted service, white-label product, OEM offering, or resale without the applicable commercial rights.

Code under `src/editions/**` and `web/src/editions/**` is outside the automatic scope of the Community/Core license. Cloud edition code currently present in those paths is governed by [LICENSE-CLOUD.md](LICENSE-CLOUD.md).

See also:

- [Commercial licensing](COMMERCIAL-LICENSE.md)
- [Trademark policy](TRADEMARKS.md)
- [Notice](NOTICE.md)

The license documents currently included in this public-readiness branch are **pre-release candidates and require qualified legal review before the repository is made public**.

---

**Woobe** is built around one operating principle: the AI product you publish should be versioned, reproducible, observable, and controllable in production.
