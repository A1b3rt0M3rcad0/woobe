# Woobe CLI

The native Woobe client, packaged for Linux, macOS and Windows on x64 and arm64.
Node.js 22 or newer is required for the npm launcher. Go is not required.

Run without a global installation:

```sh
npx --package=woobe-cli woobe version
npx --package=woobe-cli woobe help
```

Or install once:

```sh
npm install --global woobe-cli
woobe version
```

Pin an exact version for repeatable automation:

```sh
npx --package=woobe-cli@0.13.7 woobe version
```

The package contains all six native executables. Installation needs no lifecycle
scripts or external binary downloads; `npm install --ignore-scripts` works.
Arguments, stdin, output and exit codes pass directly to the native client.

## Connect your Workspace

In Woobe, open **Workspace settings → CLI Keys**, create a Control Key and save
the secret before closing the view. Create/select a connection and authenticate
with the masked prompt:

```sh
woobe context create woobe --api-url https://YOUR_WOOBE_API
woobe context use woobe
woobe auth login --cli-key
woobe agent list --output compact
```

The key discovers its Workspace and eligible Projects. A single eligible Project
is selected automatically; otherwise use `woobe context project select`.
Each connection retains its own protected key and Project selection.

The API URL is the backend URL. Project access comes from the key's explicit
grants. Runtime execution uses a separate Runtime Key.

For a terminal without Node, download the native archive from
[GitHub Releases](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases).
See [installation and versioning](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/INSTALLATION.md)
and the included `USAGE.md` for commands and credential handling.

The client is under active development. See
[implementation status](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/STATUS.md)
for functional coverage and known limitations. Published versions are identified by their immutable tag/source manifest.


## Coding assistant integration

Prepare the project, assistant instructions, Git exclusions and embedded skill together:

```sh
woobe init --agents codex
woobe init --agents codex-legacy
woobe init --agents claude
woobe skill status --agent codex,claude
```

Initialization is offline and requires no extra npm package, Node.js or backend
login. Run it from the project root; it creates or reuses the development registry.
For standalone `woobe skill install`, `--project-dir` selects another project
and `--agent codex-legacy` targets `.codex/skills`. `woobe-cli-skill` remains an
optional independent npm installer. See
[skill installation and host layouts](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/AGENT_SKILL.md).

Integrated init preserves existing registry identity and custom instructions; `--dry-run` previews changes. See [project setup](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/PROJECT_SETUP.md). `woobe skill install --agent codex` remains available for skill-only installation.
