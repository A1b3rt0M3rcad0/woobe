# Woobe — Control Plane for Production AI Agents

**Build, deploy and operate AI agents like production software.**

Woobe is an **API-first, source-available control plane and runtime for building and operating Agents and Agent Networks in production**. Version prompts, models, tools and knowledge; validate changes through controlled environments; publish immutable releases; execute through a production runtime; and trace exactly what happened.

Woobe sits between your application and the AI execution layer so your product does not have to become its own agent platform.

> **Pre-1.0:** Woobe remains pre-stable. Public APIs and deployment contracts may evolve between minor versions; review release and upgrade notes before updating.

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

## Woobe CLI

Use the external [Woobe CLI](https://github.com/A1b3rt0M3rcad0/woobe-cli) to manage
Workspaces and Project resources, validate manifests and execute released Agents
and Networks. Download the native binary for Linux, macOS or Windows from
[CLI releases](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest), or run
the public container package:

```bash
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest version
```

Create a Control Key under **Workspace settings → CLI Keys**, choose its roles
and Project grants, then configure the CLI with your backend API URL. Runtime
execution uses a separate Runtime Key. See [the CLI guide](docs/CLI.md) for
installation, credentials, contexts and commands.

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
- [CLI installation and usage](docs/CLI.md)
- [Portable Package API and implementation status](docs/CLI_PACKAGES.md)
- [Published container packages](docs/runbooks/container-packages.md)
- [Upgrading](docs/UPGRADING.md)
- [Runtime documentation](docs/runtime/)
- [Architecture Decision Records](docs/adr/)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Licensing model](LICENSING.md)
- [Releasing](RELEASING.md)

## Licensing

Woobe has two explicit software boundaries: **Core** and **Enterprise**.

### Core

The following packages are licensed under the **Woobe Core Sustainable Use License 1.0** in [`LICENSE.md`](LICENSE.md), except third-party components or files carrying their own license notice:

| Package | Role | License |
| --- | --- | --- |
| `packages/woobe-core` | Product Core, bounded contexts, runtime contracts and migrations | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-api` | API process | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-workers` | Worker process | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-runtime-client` | Shared browser Runtime protocol and observer primitives | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-ui` | Shared UI components and design tokens | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-frontend` | Administrative control-plane frontend | **Woobe Core Sustainable Use License 1.0** |
| `packages/woobe-embed` | ChatSurface browser artifact | **Woobe Core Sustainable Use License 1.0** |

Core is source-available, self-hostable and usable in production. It may power your own commercial applications, be distributed as a component of a permitted application, and be used for genuine technical services on a customer's own deployment. The license **prohibits selling the Woobe platform itself or supplying paid access to it**, including a renamed fork, a hosted or managed instance, a general-purpose runtime API offering or a paid bundle. An Enterprise production authorization does not grant resale rights.

### Enterprise

`packages/woobe-ee/**` is the Enterprise boundary, including copies, modifications and compiled forms of that material. [`LICENSE_EE.md`](LICENSE_EE.md) permits defined non-production evaluation, development and testing. **Production Use requires a valid Enterprise authorization expressly granted by Woobe in writing.** Source access and installation do not grant production rights.

Independent integration code in API or other Core packages remains Core when it imports or invokes EE. Enterprise material retains its own terms; sharing a process or container does not merge the licenses.

### Brand and third-party software

Woobe names, logos and distinctive brand assets are governed separately by [`TRADEMARKS.md`](TRADEMARKS.md). The software licenses and Enterprise production authorization grant no right to sell the platform under the Woobe brand or claim official status. Legitimate installation identification and truthful descriptive references are permitted under that policy.

Third-party software remains governed by its original licenses. See [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md) and [`NOTICE.md`](NOTICE.md).

[`LICENSING.md`](LICENSING.md) explains the practical boundary between using Core to power your own product and reselling the Woobe system itself.

## Contributing

The integration branch is `master`. Feature and fix branches should start from `master` and target `master` through focused pull requests.

External contributors must accept the [`Woobe Contributor License Agreement`](CONTRIBUTOR_LICENSE_AGREEMENT.md). Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.
