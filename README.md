# Woobe — Control Plane for Production AI Agents

**Build, deploy and operate AI agents like production software.**

Woobe is an **API-first, source-available control plane and runtime for building and operating Agents and Agent Networks in production**. Version prompts, models, tools and knowledge; validate changes through controlled environments; publish immutable releases; execute through a production runtime; and trace exactly what happened.

Woobe sits between your application and the AI execution layer so your product does not have to become its own agent platform.

> **Pre-release:** Woobe is under active development toward its first public release. Public APIs, deployment contracts and licensing text should still be treated as pre-release.

## Key Capabilities

- **Agents as Versioned Software** — Manage prompts, model configuration, tools, knowledge, output contracts and runtime configuration as controlled artifacts instead of mutable production state.
- **Immutable Releases & Rollback** — Develop freely, validate in Staging, publish immutable Agent and Network Releases, and restore previous working versions without reconstructing historical configuration.
- **Agent Networks** — Compose multiple Agents into first-class Networks with their own versions, releases, Sessions, Runs and Traces.
- **Production Runtime** — Execute Agents and Networks through synchronous, streaming and asynchronous runtime paths under the same Run model.
- **Tracing & Observability** — Record execution events, release provenance, versions, usage and runtime evidence for every Run.
- **Knowledge / RAG** — Organize Project knowledge with Collections and Documents and preserve exact indexed knowledge state through Vector Snapshots.
- **Tools & Providers** — Connect external capabilities through HTTP and MCP while keeping credentials and execution policy server-side.
- **ChatSurface** — Publish released Agents and Networks through an independently deployable browser-facing conversational surface.
- **Self-Hostable Core** — Run Woobe Core on your own infrastructure.

## From Draft to Production

```text
Configure
   ↓
Development / Draft
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

Production execution is release-based. Mutable Draft configuration should never silently change a released workload.

## Core Model

| Concept | Responsibility |
| --- | --- |
| **Organization** | Commercial boundary for ownership, members, plan, limits and Projects. |
| **Project** | Technical isolation boundary for Agents, Networks, Tools, Knowledge and runtime data. |
| **Agent** | Configurable AI execution unit. |
| **Agent Release** | Immutable snapshot of an Agent configuration. |
| **Agent Network** | Versioned composition of Agents. A Project may own multiple Networks. |
| **Network Release** | Immutable snapshot of Network composition and bindings. |
| **Session** | Long-lived conversational context. |
| **Agent Run** | One finite logical Agent execution. |
| **Network Run** | One finite Network execution coordinating related Agent Runs. |
| **Trace** | Observable evidence of what occurred during execution. |
| **Collection** | Operational aggregate for Knowledge/RAG content. |
| **Vector Snapshot** | Versioned representation of the exact indexed knowledge state. |
| **Tool** | External Agent capability exposed through HTTP or MCP. |
| **ChatSurface** | Browser-facing conversational surface for released Agents or Networks. |

## Quick Start

Woobe Core's supported self-host topology is the root `compose.yaml`.

Requirements:

- Docker with Docker Compose
- Python 3 for initial environment generation

```bash
python scripts/generate_self_host_env.py
docker compose up -d --build
```

Then open:

```text
Web UI:      http://localhost:8080
API:         http://localhost:8000
ChatSurface: http://localhost:8081
```

For public exposure, TLS, secrets, backup, restore and upgrade requirements, see [`docs/SELF_HOSTING.md`](docs/SELF_HOSTING.md).

## Repository

```text
packages/   product and distributable artifacts
tooling/    development and architecture tooling
tests/      repository and cross-system validation
scripts/    operational and CI automation
docs/       architecture, runtime and operations documentation
docker/     Docker-specific support and validation assets
deploy/     optional deployment overlays
.github/    GitHub workflows and repository automation
```

Product packages:

```text
packages/
├── woobe-core/
├── woobe-api/
├── woobe-workers/
├── woobe-frontend/
├── woobe-embed/
└── woobe-ee/
```

`woobe-core` is the product Core. API and Workers may depend on Core; Core must not depend on API, Workers, Enterprise implementation or engineering tooling.

See [`packages/README.md`](packages/README.md), [`tooling/README.md`](tooling/README.md), [`tests/README.md`](tests/README.md) and [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

## Resources

- [Architecture](docs/ARCHITECTURE.md)
- [Self-hosting](docs/SELF_HOSTING.md)
- [Upgrading](docs/UPGRADING.md)
- [Runtime documentation](docs/runtime/)
- [Architecture Decision Records](docs/adr/)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Licensing model](LICENSING.md)
- [Public release checklist](docs/PUBLIC_RELEASE_CHECKLIST.md)

## Licensing

Woobe has two explicit software boundaries: **Core** and **Enterprise**.

### Core

The following packages are licensed under the **Woobe Core Sustainable Use License 1.0** in [`LICENSE.md`](LICENSE.md), except third-party components or files carrying their own license notice:

| Package | Role | License |
| --- | --- | --- |
| `packages/woobe-core` | Product Core, bounded contexts, runtime contracts and migrations | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-api` | API process | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-workers` | Worker process | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-frontend` | Administrative control-plane frontend | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-embed` | ChatSurface browser artifact | **Woobe Core Sustainable Use License 1.0** |

Core is source-available and self-hostable. It may be used internally and may power a separate commercial product. The license does **not** allow Woobe itself, a rebranded fork, or substantially equivalent Woobe control-plane functionality to be commercially resold, white-labeled, OEM-supplied or offered as the product/service being sold without a separate written agreement.

### Enterprise

`packages/woobe-ee` is the separately licensed Enterprise boundary. It is not covered by the Core license grant. See [`LICENSE_EE.md`](LICENSE_EE.md).

### Brand and third-party software

The software license does not grant a general right to use the Woobe name, logo or brand for a third-party commercial service. See [`TRADEMARKS.md`](TRADEMARKS.md).

Third-party software remains governed by its original licenses. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`NOTICE.md`](NOTICE.md).

[`LICENSING.md`](LICENSING.md) explains the practical boundary between using Core to power your own product and reselling the Woobe system itself.

## Contributing

The integration branch is `master`. Feature and fix branches should start from `master` and target `master` through focused pull requests.

External contributors must accept the [`Woobe Contributor License Agreement`](CONTRIBUTOR_LICENSE_AGREEMENT.md). Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.
