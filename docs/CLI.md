# Woobe CLI

[woobe-cli](https://github.com/A1b3rt0M3rcad0/woobe-cli) is the external Go client
for the Woobe control plane and runtime. Its versions and releases are independent
of the Woobe platform. The backend authorizes every operation.

## Install

Open [the latest CLI release](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest)
and download your platform archive and `SHA256SUMS`:

| System | Architecture | Archive suffix |
| --- | --- | --- |
| Linux | x64 / arm64 | `linux_amd64.tar.gz` / `linux_arm64.tar.gz` |
| macOS | Intel / Apple Silicon | `darwin_amd64.tar.gz` / `darwin_arm64.tar.gz` |
| Windows | x64 / arm64 | `windows_amd64.zip` / `windows_arm64.zip` |

Verify the archive checksum before extracting. For example, with the Linux x64
archive from release `v0.1.4` and its checksum file in the same directory:

```bash
sha256sum --check --ignore-missing SHA256SUMS
tar -xzf woobe_0.1.4_linux_amd64.tar.gz
./woobe version
./woobe help
```

On macOS, use `shasum -a 256` and compare the result with `SHA256SUMS`. On Windows,
use `Get-FileHash -Algorithm SHA256`, extract the ZIP and run `.\woobe.exe version`.
Place `woobe` or `woobe.exe` in a directory on `PATH` to run it from any directory.
The native binaries require no Go, Node.js or npm installation.

The public GHCR package supports Linux amd64 and arm64:

```bash
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest version
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest help
```

Pin a version such as `:0.1.4` for automation. The image runs as UID 10001; a
persistent configuration directory mounted at `/data` must be writable by that
UID. See the client's [installation guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/v0.1.4/docs/INSTALLATION.md).

## Create a Workspace CLI Key

As a Workspace owner or authorized administrator:

1. Open **Workspace settings → CLI Keys → Create CLI key**.
2. Enter a name and select the Workspace role or permissions you need.
3. Add each Project grant separately and select its Project role. For read-only
   resource access, select **Project Reader**; other predefined roles cover
   editing, version building, production publishing and observation.
4. Choose an expiration date using the calendar. The key is valid through that
   local day and expires at the following local midnight.
5. Create the key and copy its secret before closing the result view.

No role is selected by default. A Workspace grant alone does not grant access
to Project resources. Roles outside your delegable permissions or conditions
are unavailable. Category revisions are pinned when the key is issued; changing
a role definition does not silently change existing grants.

The secret is shown only in the issuance view. Rotation immediately replaces it;
revocation immediately blocks the key. Import the replacement secret into the
CLI after a rotation. See [Control Plane authority](security/CONTROL_PLANE.md)
for the complete permission, delegation and revision rules.

## Connect the CLI

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


## Discover and validate operations

```bash
woobe help --output json
woobe doctor
woobe schema --command "project agent create" --kind input
woobe server-schema --command "project agent create"
woobe validate-input --command "project agent create" --file agent.json
woobe project agent create --file agent.json --dry-run
```

Local schemas describe CLI invocation. Server schemas describe the deployed API.
Input validation and dry-run do not create resources or grant authority. Inspect
the chosen command's help and schema before sending a mutation.

## Manifests and runtime

```bash
woobe manifest validate --file resources.json
woobe manifest plan --file resources.json
woobe manifest apply --file resources.json --checkpoint apply-checkpoint.json --yes
```

Keep the same manifest and checkpoint when resuming. Resource updates require
explicit IDs; the client does not infer an update target by name. Exports can
be incomplete projections and are not automatically safe to replay as imports.

A Control Key manages resources. Agent and Network execution uses a separate
Runtime Key created in Project settings with the appropriate target and scopes:

```bash
woobe auth credential import --name runtime --stdin < runtime.key
woobe context runtime-credential attach woobe --runtime-credential runtime
woobe runtime target run TARGET --target-kind agent --file run.json --yes
```

Keep `runtime.key` private. Use `--target-kind network` for a Network target.
The CLI never falls back to a Control Key for runtime execution. See the client's
[usage guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/v0.1.4/docs/USAGE.md)
for run input, streaming, checkpoints and output contracts.

## Updates and release ownership

Update the CLI using the latest published native archive or a pinned GHCR tag.
CLI distribution is maintained in `woobe-cli`; the platform release process
remains [RELEASING.md](../RELEASING.md). npm installation and its trusted publisher are maintained in the CLI repository.

The current client implements the reviewed operation catalog, with remaining
design work recorded in its status documentation. A published CLI release does
not imply completion of every planned client feature.

Before deploying the platform's Control Key support, follow [UPGRADING.md](UPGRADING.md)
and apply migrations through `0077`. Existing human credentials and Project
Runtime Keys remain separate from the new Workspace Control Keys.

## Managed YAML development

A matching development-capable CLI and backend support an optional local
`.woobe-config`. `woobe init --context local` initializes a registry rooted at
`.woobe/`; ordinary auth, runtime, API and standalone package commands remain
independent of that file.

```sh
woobe agent UUID pull --alias support
# Edit .woobe/agents/support/agent.yaml and registered dependencies.
woobe agent "@support" diff
woobe agent "@support" validate
woobe agent "@support" push
woobe network UUID pull --alias helpdesk
woobe network "@helpdesk" push
```

UUIDs, typed aliases and linked paths are supported. Initial pull also accepts
an exact remote name. `sync` aliases pull; reference-first `update` aliases push.
A pull can select Draft, current Staging, an immutable Release version, or current
Production. Push always updates Draft, preserving the native Agent/Network UUID.
Stage, publish and activate explicitly after reviewing the Draft.

The package registry binds each resource UID within its Project and registry.
A synchronization plan carries complete native revision evidence and separates
immutable Network constituents from mutable Agent Drafts. Shared Tool, Skill and
Knowledge definitions are reused when proven unchanged; changed dependencies
use copy-on-write. Models resolve through active native Provider connections.
Provider YAML contains only public connection intent and credential references.

Agent authoring writes atomically update the native Draft and its Agent
projection. `If-Match` guards direct Agent updates and Save Draft requests; stale
revisions fail with HTTP 409. The frontend uses the revision associated with its
editor baseline. CLI pull performs a semantic three-way merge; conflicts leave
local descriptors and registry state untouched.

`diff` includes dependency and declared support-file changes offline. Local
schema validation does not claim server authorization or runtime readiness.
Private `.state/` contains destination bindings, base revisions and durable push
checkpoints, is excluded from Git, and is never included in compiled packages.


### Execute saved Agent tests from YAML

After pushing author changes, explicitly stage and test the saved native snapshot:

```sh
woobe agent "@support" stage --yes
woobe agent "@support" test --file support-test.yaml --yes
woobe agent "@support" publish --notes "Validated support changes" --yes
woobe agent "@support" activate --version 1.2.0 --notes "Deploy reviewed release" --yes
```

A testcase contains `message`, optional `external_context`, and optional
`expected_output`. Execution records the actual answer, parsed output, Run ID,
latency and validation errors on the selected native Release Test. Current
Staging is the default; `--env draft`, `--env production`, or `--env release
--version VERSION` select other saved snapshots. Failed execution/assertions exit
with code 6 and include the recorded result. Both Agent versioning and Run
execution permissions are checked before execution. Network uncertainty is never
retried automatically.

Development synchronization reuses proven unchanged Knowledge collections,
documents and vector snapshots. Changed chunking or embedding configuration
creates an immutable snapshot containing only declared document identities.
Failed builds retain their history and get a separate retry version. Skill author
edits preserve the native Skill namespace and fork immutable content versions.
Provider/Model impact includes frozen Network versions and Chat Surfaces, not
only the current Agent Draft.

Migration `0081` retains committed preparation identities, including a Knowledge
collection prepared before a failed vector build. Recovery must reuse those
identities and reject roots changed by another client. Apply it together with
`0080` before deploying the managed development endpoints.


### Providers and Surfaces in the development registry

A Provider author file contains public connection intent. `credential_ref` is
optional for a new definition: use `woobe resources bind provider @alias UUID` to
verify a native active credential in this Project. Its identity stays private and
is reused by subsequent pulls. A second local Provider cannot bind that same
credential. Provider impact includes embedding Knowledge dependencies through
frozen Agent Releases, Networks and Surfaces.

Surface author YAML has `spec.target_ref` to the stable registered Agent/Network
key. `surface UUID pull --alias chat` requires the target to be pulled first;
`surface @chat create --yes` resolves its current Production Release. `pull`,
`diff`, `status`, `validate` and `push` use the registry and preserve native identity.
Push compares `updated_at` and sends quoted `If-Match`, rechecked under a row lock.
Independent edits merge, conflicts stop. The target is immutable and configuration
push never refreshes or activates its Release. Native Surface configuration can
affect active Surfaces: disable first when changes must stay offline. Unknown
create outcomes persist an intent that blocks replay until explicit UUID pull.

Registered bulk operations include Surfaces after their targets. Agent/Network
dry runs validate exact server package plans; Surface dry runs report local and
destination/CAS identity checks, with final native DTO validation on apply.
