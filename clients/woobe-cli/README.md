# Woobe CLI

Develop resources without handling Provider secrets: declare remote keys with
`woobe project configuration declare PRIMARY_API_KEY`, then inspect an Agent or
Network with `woobe project configuration check agent AGENT_UUID --env draft`.
Use `woobe project configuration summary --env draft` for a bounded Project overview.
Operators fill values and approve destinations in Woobe Environments; see
[Project configuration](docs/CONFIGURATION.md).

Deploy exact evaluated Agent/Network Releases with `woobe agent UUID deploy --from release --release RELEASE_UUID --notes "Approved delivery" --yes`. Local YAML delivery and protected CI recovery are documented in [Deployment](docs/DEPLOYMENT.md) and [CI deployment](docs/CI_DEPLOYMENT.md).

Prepare a checkpointed isolated Draft with `stage --revision REVISION_ID --yes`
and inspect `candidate CANDIDATE_UUID`. This freezes the exact retained closure
without changing native environments or publishing; see the
[ASaC workflow](docs/ASAC.md#prepare-an-exact-immutable-candidate).

Command-line client for the [Woobe](https://github.com/A1b3rt0M3rcad0/woobe)
control plane and runtime. Manage Workspace and Project resources, validate
manifests, publish Agent and Network releases and execute released targets.
The backend authorizes every operation.

Development clones can recover accepted native identities with
`woobe agent '@support' bindings recover`; see [ASaC](docs/ASAC.md) for
closure validation, explicit Provider binding and stale-generation protection.

## Coding assistant skill

The CLI bundles a small portable skill, offline references and YAML templates
for Codex, Claude Code, Copilot, Cursor and other Agent Skills-compatible hosts.
Prepare the project and assistant together from its root:

```sh
woobe init --agents codex
# Alternatives:
woobe init --agents codex-legacy
woobe init --agents claude
# Or several hosts:
woobe init --agents codex,claude
```

This creates/reuses `.woobe-config`, installs embedded skills, adds managed
`AGENTS.md`/host instructions and ignores private `.state/` and `.woobe-lab/`.
Repeated initialization preserves resource identity and custom instructions;
`--dry-run` previews setup. No backend, Node.js or extra package is required.
Remote operations still require a saved connection and CLI Key.

For skill-only or user-scope installation, use `woobe skill install --agent codex`
and `woobe skill status/uninstall`. Runtime Skills remain separate under
`woobe project skill`.

| Distribution | Purpose |
| --- | --- |
| `woobe-cli` / native binary | Integrated project init plus offline skill management |
| `woobe-cli-skill` (optional npm) | Same skill plus independent `woobe-skill` installer, Node.js 22+ |

See [project setup](docs/PROJECT_SETUP.md), [standalone skill installation](docs/AGENT_SKILL.md)
and the [documentation index](docs/INDEX.md). New flags become available in npm
`latest` only after the corresponding release is published.

## Develop locally with YAML

`woobe init`, then `woobe agent UUID pull --alias support`; edit the YAML and
run `woobe agent "@support" diff` followed by `woobe agent "@support" push`.
Networks use the same workflow. Push writes Draft and preserves the native root
UUID. The optional registry shares Providers, Models and other dependencies
across artifacts. Generated YAML uses two-space indentation and multiline
instruction blocks; registered `.json` files remain indented JSON.
See [managed development](docs/USAGE.md#pull-edit-yaml-push-draft)
for environments, conflicts and recovery. Requires a matching Woobe backend
with development synchronization capabilities.

## Install and run

Download your platform archive and `SHA256SUMS` from
[the latest GitHub Release](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest).
The published `v0.13.7` release includes all six targets:

| System | x64 | arm64 |
| --- | --- | --- |
| Linux | `linux_amd64.tar.gz` | `linux_arm64.tar.gz` |
| macOS | `darwin_amd64.tar.gz` | `darwin_arm64.tar.gz` |
| Windows | `windows_amd64.zip` | `windows_arm64.zip` |

Verify the checksum, extract the archive and place `woobe` or `woobe.exe` on
`PATH`. For example, on Linux x64:

```bash
sha256sum --check --ignore-missing SHA256SUMS
tar -xzf woobe_0.13.7_linux_amd64.tar.gz
./woobe version
./woobe help
```

On macOS, compare `shasum -a 256` with the checksum file. On Windows, use
`Get-FileHash -Algorithm SHA256`, extract the ZIP and run `.\woobe.exe version`.
No Go, Node.js or npm installation is required to use the native binaries.

The public [GitHub Packages image](https://github.com/users/A1b3rt0M3rcad0/packages/container/package/woobe-cli)
supports Linux amd64 and arm64:

```bash
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest version
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:0.13.7 help
```

Pin a version for automation. Mount persistent configuration at `/data`, writable
by UID 10001. See [installation and container usage](docs/INSTALLATION.md).

## npm installation

Each automatic release publishes the same validated version to npm. Node.js 22+ is required; Go is not.

```sh
npm install --global woobe-cli
npx --yes --package=woobe-cli woobe version
```

The package bundles all six executables and works with `--ignore-scripts`.
See [one-time npm publisher setup and recovery](docs/INSTALLATION.md#npm-publisher-setup-owner-once).

## Connect to Woobe

Create a Control Key at **Workspace settings → CLI Keys → Create CLI key**.
Choose the Workspace role you need and add Project grants separately, selecting
a role for each Project. Set an expiration date and copy the secret before
closing the issuance view. Rotation replaces the secret immediately.

```sh
woobe context create minha-woobe --api-url https://YOUR_WOOBE_API
woobe context use minha-woobe
woobe auth login --cli-key
woobe project agent list
```

Paste the key at the masked prompt; do not put it in arguments. The CLI validates
it against this connection, discovers its Workspace and selects a single eligible
Project automatically. For several Projects, choose by name/number. Switch later
with `woobe context project select` or `woobe context project select production`.
No Project grants means Workspace-only authentication. No UUIDs or environment
variables are required. Linux/macOS store credentials in private files; Windows
uses the current user's Credential Manager. Reopening the terminal retains the
connection. Each named context has its own key and selected Project.

For automation, pipe a secret from your secret manager into
`woobe auth login --cli-key --stdin --select-project production --no-input`.
Without a selection, multiple Projects produce `project_selection_required`.
`woobe auth status` inspects the current key and scope;
`woobe auth logout --cli-key` clears local authentication without server revocation.
Changing the API URL requires login again. Runtime Keys remain separate.

## Discover and automate

Interactive terminals now show concise tables and labeled results. Existing
redirected JSON remains compatible. For AI agents, use `--output compact` and
select the fields needed for the next action:

```sh
woobe agent list
woobe agent list --output compact --fields id,name,status
woobe agent get AGENT_ID --wide
```

`--output json` retains the complete response. `doctor` summarizes checks without
dumping OpenAPI. See [output formats](docs/OUTPUT.md) and the
[measured before/after comparisons](docs/OUTPUT_EXAMPLES.md).

```bash
woobe help --output json
woobe doctor
woobe schema --command "project agent create" --kind input
woobe validate-input --command "project agent create" --file agent.json
woobe manifest validate --file resources.json
woobe manifest plan --file resources.json
woobe manifest apply --file resources.json --checkpoint apply-checkpoint.json --yes
```

Preserve the manifest and checkpoint when resuming. Exports can be incomplete
projections; they are not automatically safe to replay. The [usage guide](docs/USAGE.md)
documents Agent/Network configuration, publication, streaming, protected inputs
and recovery.

Runtime execution uses a separately selected Runtime Key. The CLI never falls
back to a Control Key for Agent or Network execution:

```bash
woobe auth credential import --name runtime --stdin < runtime.key
woobe context runtime-credential attach woobe --runtime-credential runtime
woobe runtime target run TARGET --target-kind agent --file run.json --yes
```

Keep `runtime.key` private. Use `--target-kind network` for a Network.

## Develop and release

Use the Go toolchain pinned in `go.mod`. Development commands:

```bash
make build
bin/woobe help --output json
make check
make package
```

Source builds use the reviewed `VERSION` floor. Published binaries embed their
release version and exact source commit. CLI and platform versions are independent.

The Release CLI workflow calculates SemVer, validates six native archives,
creates an immutable tag, publishes GitHub Releases and the GHCR version, and
updates `latest` for successful stable releases. Once that workflow is integrated
into `master`, every push to `master` starts this complete flow. It never merges
development PRs or rewrites source versions automatically.

Develop in a branch, open a PR to `master`, pass CI and merge the reviewed change.
Use Conventional Commit subjects, including the final squash subject:

| Change | Version increment |
| --- | --- |
| `fix(cli): correct an input` | PATCH |
| `feat(cli): add a command` | MINOR |
| `feat(cli)!: change a contract` | MINOR before 1.0; MAJOR after 1.0 |

Explicit `v<VERSION>` tags can release the exact tagged source through the same
CI gates before master integration. Rerunning a release recovers that version;
it does not create another version. Published tags, assets and image versions
must never be overwritten. See [release calculation and recovery](docs/INSTALLATION.md).
The same tested release is also published to npm after the one-time publisher setup.

## Coverage and documentation

Unified discovery includes 241 handlers and 190 HTTP operations. The full design
remains incomplete: the audited plan contains 66/101 completed deliveries
(65.3%), with partial deliveries receiving no credit. This planning measure does
not replace acceptance of a particular operation or imply full production coverage.

- [Implementation status and limits](docs/STATUS.md)
- [Usage and command catalog](docs/USAGE.md), [operations](docs/OPERATIONS.md)
- [CI and native validation](docs/CI.md)
- [Plan assessment](docs/COMPLETENESS.md) and [remaining requirements](docs/REMAINING.md)
- [Control Plane authority](https://github.com/A1b3rt0M3rcad0/woobe/blob/master/docs/security/CONTROL_PLANE.md)

Backend integration and Workspace CLI Keys are delivered by
[Woobe PR #177](https://github.com/A1b3rt0M3rcad0/woobe/pull/177).
Server capabilities require advertisement and authorization; the CLI cannot grant
permissions the server does not provide.

## Portable packages

See [portable Agent and Network packages](docs/PACKAGES.md) for offline validation, approved plans, durable import/recovery, Knowledge rebuilding and complete snapshot export. The paired draft PRs carry the supported CLI/server revisions and qualification evidence.

### Portable YAML export/import

```powershell
woobe package export agent "Support Agent"
woobe package export agent AGENT_UUID --env production
woobe package export agent AGENT_UUID --env release --version v1.0.20261007.01
woobe package validate ./support-agent --locked
# During local author editing (does not certify capture integrity):
woobe package validate ./support-agent --structure-only
woobe package bindings ./support-agent --destination ./destination.yaml
woobe package import ./support-agent --bindings ./destination.yaml --wait
```

Export accepts a name or UUID, defaults to draft and `./normalized-name`, and writes
readable YAML with dependencies. Fill bindings with destination identities before
importing; packages without requirements need no bindings. Import creates draft
resources and manages its private recovery checkpoint automatically. See
[Package guide](docs/PACKAGES.md) for review, environments and recovery. Use
`woobe package --help` or `woobe help package export agent --output compact`.


Managed development includes explicit creation and safe recovery:

```sh
woobe resources clone agent '@support' --alias support-next
woobe agent '@support-next' create --yes
woobe resources diff
woobe resources push --dry-run
woobe agent '@support' reconcile
```

See [local identities, bulk operations and recovery](docs/USAGE.md#explicit-local-identities-and-recovery).


### Repository-local YAML development

`.woobe-config` is optional and is used only by development commands. Native UUID
API operations, authentication and runtime commands work without it.

```sh
woobe init --root .woobe
woobe agent AGENT_UUID pull --alias support
woobe agent '@support' diff
woobe agent '@support' push --yes
woobe agent '@support' stage --yes
woobe agent '@support' test --file testcase.yaml --yes
woobe agent '@support' publish --notes "Reviewed change" --yes
```

Providers, Models, Tools, Skills, Knowledge, Prompts and Contracts are registered
once and reused through typed local references. Surface authoring uses the same
registry and native identities. See [Provider bindings and Surface workflows](docs/DEVELOPMENT.md)
and [local development and recovery](docs/USAGE.md#explicit-local-identities-and-recovery).
The development server additions were delivered in merged [Woobe PR #179](https://github.com/A1b3rt0M3rcad0/woobe/pull/179).

## Contributing

See [ASaC tracking and history](docs/ASAC.md) for immutable local revisions,
origin locks, guarded local author-source checkout/rebase, isolated Draft selection/recovery and explicit
remote observations of Agent/Network selections.

Read [AGENTS.md](AGENTS.md) for repository maintenance instructions, including
which help, documentation and assistant skill files to update with CLI changes,
how to regenerate derived docs and which validation applies.

Isolated revision catalogs can be mirrored with
`woobe agent @support history fetch --revisions` (and Network equivalents).
This fetch preserves author files and the working head; it reports metadata
coverage separately from object availability. See [ASaC workflows](docs/ASAC.md).

`woobe agent @support revision hydrate REVISION_ID` retrieves a verified
retained executable object after catalog fetch. Author source and credentials
remain separate; hydration preserves local working files. When source custody is retained on the server, hydration also verifies the original YAML, comments and support files through the recorded compiler recipe. Use guarded checkout to restore them.

Evaluate an isolated ready Candidate with `woobe agent UUID test --candidate CANDIDATE_UUID --file suite.yaml --yes` (also supported for Networks). See the [versioned YAML suite and reconciliation workflow](docs/DEVELOPMENT.md#exact-candidate-evaluation).

Publish an exact evaluated Agent with `woobe agent '@support' publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes 'Validated update' --yes`. This does not activate Production; see [exact publication and recovery](docs/ASAC.md#publish-an-exact-evaluated-agent-candidate).

Exact Network Candidate publication and recovery use `woobe network REFERENCE publish --candidate UUID --evaluation UUID --notes REASON --yes`; this preserves Production and standalone Agent selections. See [Network publication and recovery](docs/ASAC.md#publish-and-recover-an-exact-network-candidate).

Exact evaluated Release selection is a separate workflow: create a deployment
plan, acquire its environment lease, apply once and reconcile original acceptance
after an uncertain response. See [ASaC deployment plans](docs/ASAC.md#exact-release-deployment-plans).

Project lifecycle authority: `woobe project lifecycle show`; audited YAML changes and original-operation recovery are documented in [Project lifecycle policy](docs/PROJECT_LIFECYCLE.md). The server gates legacy promotion in managed Projects.

Server-signed ASaC receipts can be exported and verified offline with an explicit
operator-confirmed root. See [signed receipts](docs/SIGNED_RECEIPTS.md) for trust pinning,
rotation, revocation and limits on freshness and Git provenance.

Trusted CI provenance is a separate, explicitly authorized workflow.
`woobe agent REFERENCE git-proof` checks committed author bytes offline;
`woobe agent UUID git-attest` attaches a trusted proof to an existing Publication.
Neither publishes nor deploys. See [trusted Git provenance](docs/GIT_PROVENANCE.md).

Portable sealed packages can be edited through verified separate copies with
`woobe package edit SOURCE --destination ./author`, then resealed with
`woobe package seal ./author --destination ./sealed`. See [Packages](docs/PACKAGES.md).
For read-only automation, `--fields "id,name" --strict-fields --output compact`
rejects absent fields; compact ASaC outputs retain continuation IDs.

Prompt/Contract capture, native test result validation, uncertain test recovery and versioned secret-file custody are described in [the recovery guide](docs/CONTRACTS_TEST_RECOVERY.md).
