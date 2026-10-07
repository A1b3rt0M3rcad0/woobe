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
remains [RELEASING.md](../RELEASING.md). npm distribution is deferred.

The current client implements the reviewed operation catalog, with remaining
design work recorded in its status documentation. A published CLI release does
not imply completion of every planned client feature.

Before deploying the platform's Control Key support, follow [UPGRADING.md](UPGRADING.md)
and apply migrations through `0077`. Existing human credentials and Project
Runtime Keys remain separate from the new Workspace Control Keys.
