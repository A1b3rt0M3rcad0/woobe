# Woobe — Control Plane for Production AI Agents

![Woobe — Product Overview](docs/assets/Woobe%20%E2%80%94%20Product%20Overview.png)

**Define, version, test, deploy and operate AI agents like production software.**

Woobe is an **API-first, source-available control plane and runtime for Agents and Agent Networks**. Develop through YAML and the CLI, work with a coding assistant, or use the Web UI. Woobe manages the releases, runtime execution and evidence behind your AI application.

Your application calls a released Agent or Network; Woobe resolves its versioned prompts, models, tools, skills and knowledge, executes the workload and records what happened.

[Quick start](#quick-start--run-your-first-agent) · [YAML and coding assistants](#develop-with-yaml-and-coding-assistants) · [Capabilities](#key-capabilities) · [Documentation](#resources) · [Licensing](#licensing)

> **Pre-1.0:** Public APIs and deployment contracts may evolve between minor versions. Review release and upgrade notes before updating.

## Why Woobe?

Production agents need more than a prompt and a model call. Teams need to know what was tested, what is running and how to recover when a change fails.

- **Ship a known configuration.** Production resolves immutable Agent or Network Releases. Editing a Draft does not silently change a released workload.
- **Build systems around your product.** Create a support Agent with HTTP/MCP tools and Project knowledge, compose specialists into an Agent Network, or expose a released target through ChatSurface.
- **Understand execution.** Sessions preserve context; Runs record finite executions; Traces expose events, release provenance and usage.
- **Own the deployment.** Self-host Core and connect your application through runtime APIs, the CLI or ChatSurface.

Woobe provides the control plane and runtime between your application and its AI execution layer. Frameworks can help implement agent behavior; Woobe adds a shared lifecycle for configuration, validation, releases and operation. ChatSurface is one way to deliver that runtime to users.

## Quick start — Run your first Agent

You need Docker with Docker Compose, Python 3 and credentials for a supported model Provider. CLI steps also require the native [Woobe CLI](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest), or Node.js 22+ for npm installation.

### 1. Start Woobe Core

```sh
git clone https://github.com/A1b3rt0M3rcad0/woobe.git
cd woobe
python scripts/generate_self_host_env.py
docker compose up -d --build
```

Open the Web UI at **http://localhost:8080**. The API is at **http://localhost:8000** and ChatSurface at **http://localhost:8081**. The environment generator creates independent bootstrap secrets; keep the generated `.env` private.

### 2. Create and validate an Agent

On a fresh instance, register the instance owner and create or select a Project. Connect your model Provider with its credentials, then create a **Support** Agent and select an available model.

For a first prompt, use:

```text
Help the user investigate an unavailable service.
Ask for missing details, suggest concrete diagnostic steps,
and state what you cannot verify. Never invent a diagnosis.
```

Save Draft, stage the configuration and run a test such as **“Our API is returning HTTP 503. What should I check?”**. Inspect the result before publishing an immutable Agent Release and explicitly activating that version in Production. Projects enforcing qualified delivery use the [deployment workflow](docs/CLI_DEPLOYMENT.md).

### 3. Connect the CLI

Install the native binary from [CLI releases](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest), or install through npm:

```sh
npm install --global woobe-cli
woobe version
```

Create a Control Key under **Workspace settings → CLI Keys**, with the roles and Project grants needed for your work. Connect to the backend and paste that key at the masked prompt:

```sh
woobe context create local --api-url http://localhost:8000
woobe context use local
woobe auth login --cli-key
woobe project agent list
```

Select the Project when prompted. Copy the Support Agent's UUID from the list for `AGENT_UUID` below.

### 4. Execute and inspect a production Run

Create a separate **Runtime Key** in Project settings, scoped to your Agent and runtime operations. Save it in a private `runtime.key` file outside the repository and import it from that location:

```sh
woobe auth credential import --name runtime --stdin < runtime.key
woobe context runtime-credential attach local --runtime-credential runtime
```

Save this request as `run.yaml`:

```yaml
input: "Our API is returning HTTP 503. What should I check?"
options:
  metadata:
    source: readme-quick-start
```

Execute the released Agent, then use the returned Run ID to inspect its execution:

```sh
woobe runtime target run AGENT_UUID --target-kind agent --file run.yaml --yes
woobe runtime target observe AGENT_UUID RUN_UUID --target-kind agent --output jsonl
```

The result includes execution identities; inspect the Run and Trace in the Web UI to see the selected release, events and usage. Reuse the returned Session ID in later requests to continue the conversation. Runtime execution uses the Runtime Key, separately from the Control Key.

For TLS, public exposure, backups and upgrades, see [self-hosting](docs/SELF_HOSTING.md). Provider calls use your configured Provider and may incur its usage charges.

## Develop with YAML and coding assistants

From your application's repository, initialize local development and the bundled assistant skill:

```sh
woobe init --context local --agents codex
# For Claude Code instead: woobe init --context local --agents claude
woobe agent AGENT_UUID pull --alias support
woobe resources list
```

Initialization prepares `.woobe-config`, embedded assistant skills and managed host instructions. Pull registers the Agent and its dependency closure under `.woobe/`. The CLI supports Codex, Claude Code, Copilot, Cursor and other Agent Skills-compatible hosts; see [project setup](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/PROJECT_SETUP.md).

A complete minimal Agent author file uses the supported `woobe-package` schema:

```yaml
format: woobe-package
schema_version: "1.0"
kind: Agent
metadata:
  key: support
  name: Support
spec:
  legacy_system_prompt: |-
    Help the user investigate an unavailable service.
    Ask for missing details and suggest concrete diagnostic steps.
    State what you cannot verify. Never invent a diagnosis.
  model:
    primary:
      ref: registered-model-key
  execution:
    strategy: standard
    config: {}
  session:
    mode: stateful
```

Edit the registered `.woobe/agents/support/agent.yaml`. Keep its exported `metadata.key` and replace `registered-model-key` with the existing Model reference from the pulled definition or `woobe resources list`. A Model reference is a registry key, not a Provider credential or a model name. Provider secrets stay on the destination; the pulled closure supplies the Project bindings.

Review and synchronize your changes:

```sh
woobe agent "@support" diff
woobe agent "@support" validate
woobe agent "@support" push --dry-run
woobe agent "@support" push --yes
```

Push updates Draft. For a Project using the native Agent lifecycle, save this testcase as `support-test.yaml`:

```yaml
message: "Our API is returning HTTP 503. What should I check?"
```

Then stage, execute the saved test and publish after inspecting the result:

```sh
woobe agent "@support" stage --yes
woobe agent "@support" test --file support-test.yaml --yes
woobe agent "@support" publish --notes "Reviewed support update" --yes
woobe agent "@support" release list --output compact
woobe agent "@support" activate --version ACTUAL_RELEASE_VERSION --notes "Deploy reviewed version" --yes
```

Use the actual published version for `ACTUAL_RELEASE_VERSION`. This testcase checks execution and output validation; add assertions for your application's acceptance criteria. Local validation alone does not certify runtime behavior.

For managed Projects and exact evaluated Agent/Network delivery, use [qualified deployment](docs/CLI_DEPLOYMENT.md). Network lifecycle behavior differs from the native Agent example above; follow the [CLI lifecycle guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/packages/woobe-cli-skill/skills/woobe-cli/references/lifecycle.md). Inspect available commands with `woobe help`; CLI and backend capabilities must match.

ASaC also exposes isolated Drafts, revisions, Candidates, evaluations, publications and deployment history through the **History & lifecycle** workbench and CLI. See [ASaC history](docs/runtime/ASAC_HISTORY.md) and the [CLI documentation index](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/INDEX.md). Git provenance is recorded or verified explicitly.

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
| **Workspace** | Account and ownership boundary for members, authority and Projects. |
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

## Woobe CLI

The external [Woobe CLI](https://github.com/A1b3rt0M3rcad0/woobe-cli) manages resources and local YAML, installs coding assistant skills, supports Agent/Network delivery and executes released runtime targets. CLI versions are independent of platform releases.

Install from [native releases](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest), npm with Node.js 22+, or use the public container:

```sh
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest version
```

See [connection and credentials](docs/CLI.md), the [current CLI documentation](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/INDEX.md) and [deployment/recovery](docs/CLI_DEPLOYMENT.md). Use the published release's documentation and help when choosing commands, and pin a CLI version for automation.

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
├── woobe-runtime-client/
├── woobe-ui/
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
- [Qualified CLI deployment and recovery](docs/CLI_DEPLOYMENT.md)
- [Portable Agent/Network Package import and export](docs/CLI_PACKAGES.md)
- [Published container packages](docs/runbooks/container-packages.md)
- [Upgrading](docs/UPGRADING.md)
- [Runtime documentation](docs/runtime/)
- [Architecture Decision Records](docs/adr/)
- [Security](SECURITY.md)
- [Contributing](CONTRIBUTING.md)
- [Licensing model](LICENSING.md)
- [Releasing](RELEASING.md)

## Licensing

Woobe has separate **Core** and **Enterprise** software boundaries.

- **Core** is source-available and self-hostable under the [Woobe Core Sustainable Use License 1.0](LICENSE.md). You may use it in production to power permitted applications and technical services on a customer's own deployment. Selling the Woobe platform itself or supplying paid access to it, including a hosted instance or renamed fork, is prohibited.
- **Enterprise** material under `packages/woobe-ee/**`, including copies and compiled forms, is governed by [LICENSE_EE.md](LICENSE_EE.md). Defined non-production evaluation, development and testing are permitted; Production Use requires express written Enterprise authorization from Woobe. That authorization does not grant platform resale rights.
- Names, logos and brand assets follow [TRADEMARKS.md](TRADEMARKS.md). Third-party software retains its original terms; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and [NOTICE.md](NOTICE.md).

See [LICENSING.md](LICENSING.md) for package coverage, integration boundaries and permitted uses.

## Platform releases

Merging a reviewed PR into `master` does **not** publish a platform release. To release, start **Actions → Release Woobe → Run workflow** on `master` and leave `version` blank. The workflow calculates SemVer from commits since the last publication, synchronizes versions through a CI-validated release PR, then publishes an immutable Git tag, [GitHub Release](https://github.com/A1b3rt0M3rcad0/woobe/releases) and the four GHCR packages: `woobe-api`, `woobe-workers`, `woobe-frontend` and `woobe-embed` for amd64 and arm64.

Developers do not bump manifests or create tags manually. See [the release procedure](RELEASING.md) for version rules, repository permissions and recovery.

## Contributing

The integration branch is `master`. Feature and fix branches should start from `master` and target `master` through focused pull requests.

External contributors must accept the [`Woobe Contributor License Agreement`](CONTRIBUTOR_LICENSE_AGREEMENT.md). Read [`CONTRIBUTING.md`](CONTRIBUTING.md) before opening a pull request.
