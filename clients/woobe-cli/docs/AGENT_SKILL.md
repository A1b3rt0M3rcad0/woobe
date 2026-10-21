# Woobe CLI skill for coding agents

For complete project setup, run `woobe init --agents codex`,
`woobe init --agents codex-legacy` or `woobe init --agents claude`. This initializes
or reuses the registry, installs the skill, adds managed `AGENTS.md`/host
instructions and ignores private `.state/` and `.woobe-lab/`. Multiple presets,
repeat initialization and `--dry-run` are supported. See
[project setup](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/PROJECT_SETUP.md).
The standalone installers described below remain skill-only and do not manage
those project files.


The CLI embeds the portable `woobe-cli` Agent Skill and installs it directly:
`woobe skill install`. It teaches a coding assistant to use Woobe efficiently;
it is different from runtime Skills uploaded to Woobe Agents. Built-in installation
needs no npm, Node.js, network, key, context or `.woobe-config`. Linux, macOS and
Windows binaries contain the same reviewed skill files as the optional npm package.

`woobe-cli-skill` remains a separate npm package with the `woobe-skill` installer
for assistants that want instructions independently of a native CLI installation.
That optional installer requires Node.js 22+. Documented Woobe workflows require
CLI 0.32.3+ for the current ASaC command references; the new built-in installer is available in CLI releases containing
this PR. Neither installer logs in, asks for keys or calls Woobe.

## Install directly from Woobe CLI

After installing a CLI release containing this feature, run from your project:

```sh
woobe skill install --agent codex
woobe skill install --agent claude
woobe skill install --agent codex,claude,copilot,cursor
woobe skill status --agent codex,claude --output compact
woobe skill uninstall --agent codex,claude --dry-run
woobe skill uninstall --agent codex,claude
```

`woobe skills` is the canonical group; singular `woobe skill` routes these four
local actions without changing runtime `woobe skill list/create/get/update/delete`.
Supported destinations can be listed with `woobe skill agents`.

```sh
woobe skill install --agent codex-legacy --scope user
woobe skill install --project-dir ./my-project --agent claude
woobe skill install --path ./custom-assistant/skills
woobe skill install --agent codex --dry-run
```

Use `--project-dir` for an existing local project; global `--project` is a Woobe
Project ID and is not a filesystem path. No backend setup is needed to install
instructions. Re-run install after upgrading the CLI to update unchanged managed
skills. The CLI and npm installer recognize each other's receipts; edited files
remain protected across both. Outputs use the normal CLI text/compact/JSON modes.

## If `--agent` is unknown after upgrading

CLI 0.13.7 does not include the built-in installer. A merge starts the release
workflow, but `npm install -g woobe-cli@latest` continues installing the previous
version until npm publication succeeds. Check the registry and executable:

```powershell
npm view woobe-cli version
woobe version
Get-Command woobe -All | Select-Object Source
```

Once the registry offers the release containing this feature, reinstall and open
a new terminal if necessary. If `woobe version` still shows an older version,
check for another executable earlier on PATH. Installing an unchanged `latest`
repeatedly cannot add commands that have not been published.

## Optional npm installation

After the package's initial publication:

```sh
npx --yes --package=woobe-cli-skill woobe-skill install --agent codex
npx --yes --package=woobe-cli-skill woobe-skill install --agent claude
```

Install in several hosts with one command, or globally install the installer:

```sh
npm install --global woobe-cli-skill
woobe-skill install --agent codex,claude,copilot,cursor
woobe-skill status --agent codex,claude,copilot,cursor --json
```

For the standalone npm installer, run from the intended project or select an
existing project with `--project DIR` (native CLI uses `--project-dir`).
Installation is explicit: `npm install` alone does not change project files,
agent settings, `AGENTS.md` or `CLAUDE.md`. No dependencies or lifecycle scripts
are used. Windows PowerShell, Linux and macOS use the same commands.
Restart/reload the assistant if it has already indexed skills; installation
cannot certify whether a particular host/version has loaded a skill.

| Preset | Project skill directory | User skill directory (`--scope user`) |
| --- | --- | --- |
| `codex` | `.agents/skills/woobe-cli` | `~/.agents/skills/woobe-cli` |
| `codex-legacy` | `.codex/skills/woobe-cli` | `~/.codex/skills/woobe-cli` (or `$CODEX_HOME/skills/woobe-cli`) |
| `claude` | `.claude/skills/woobe-cli` | `~/.claude/skills/woobe-cli` |
| `copilot` | `.github/skills/woobe-cli` | `~/.copilot/skills/woobe-cli` |
| `cursor` | `.cursor/skills/woobe-cli` | `~/.cursor/skills/woobe-cli` |
| `agents` | `.agents/skills/woobe-cli` | `~/.agents/skills/woobe-cli` |

Codex defaults to the current `.agents/skills` layout. Select `codex-legacy`
explicitly for a host expecting `.codex/skills`. Other Agent Skills-compatible
assistants can use their own skills root:

```sh
woobe-skill install --agent codex-legacy --scope user
woobe-skill install --path ./custom-assistant/skills
woobe-skill install --agent claude --dry-run
woobe-skill agents
woobe-skill --help
```

`--path` names the skills root: the installer appends `woobe-cli`. It cannot be
combined with agent/scope/project-directory options. `--scope` defaults to `project`;
project installation does not search parent directories or silently become user-wide.
Duplicate destinations are installed once.

## Update, inspect and remove

```sh
npm install --global woobe-cli-skill@latest
woobe-skill install --agent codex,claude
woobe-skill status --agent codex,claude --json
woobe-skill uninstall --agent codex,claude --dry-run
woobe-skill uninstall --agent codex,claude
```

The receipt `.woobe-skill-install.json` records package/version/source SHA and
file hashes. An unchanged managed installation can be replaced or removed.
Unmanaged files, edited files and extra files are preserved: installation/removal
stops with an explanation. Move/back up your custom skill before installing a
new managed copy. There is deliberately no force-overwrite option.

The installer preflights all requested destinations, uses per-destination locks
and directory swaps, and rolls back ordinary failures. Links/junctions, hardlinked
files, oversized files and malformed receipts are rejected. A process interruption
can leave a `.woobe-cli.install.lock` or stage/backup directory; inspect and preserve
its contents and confirm no installer is running before manual recovery. Status
and dry-run never create agent directories. Other skills/settings are retained.

## What the assistant learns

The small `SKILL.md` routes to only the needed offline reference:

- Connection/API URL, masked CLI Key login and automatic Project discovery.
- Agent/Network pull, local YAML edit, validate/diff and push to existing Draft.
- Shared Provider → Model dependencies, Tools, runtime Skills, Knowledge and Surfaces.
- Portable package export/import, destination bindings and checkpoints.
- Tests, Staging, immutable Releases, Production activation and rollback.
- Canonical administration, schema discovery, runtime and compact output.
- Conflicts, missing descriptors, registry prune and uncertain-write recovery.

Templates for a local Agent descriptor and test request are included. The Agent
template requires a real registered Model key; it is not an apply-ready example.
Authorization belongs to the user's request, host policy and Woobe backend;
the skill does not grant permission or promote environments automatically.
Network publication's native Production activation is explicitly documented.

For Codex, invoke `$woobe-cli`. For other hosts, ask to use the installed Woobe
CLI skill. Example:

> Use the Woobe CLI skill. In the selected connection, pull Agent UUID as
> @support, inspect only the relevant YAML/dependencies, propose the change and
> validate/diff it. Push only the authorized Draft changes. Report the result
> with compact output. Do not publish or activate Production.

No API key or private `.state` belongs in the skill or prompts. Set up the named
connection with `woobe context create NAME --api-url URL`, `woobe context use NAME`
and `woobe auth login --cli-key` independently.

## Versioning and initial npm publication (owner once)

Both npm packages use the same calculated release version and immutable source
commit, while the skill records its minimum supported CLI version separately.
Every distribution build includes `woobe-cli-skill-VERSION.tgz` in GitHub Release
assets, `SHA256SUMS`, `artifacts.json` and the permanent release manifest. The
skill tarball is tested offline on all six native OS/architecture runners.
PR builds do not publish to npm or create tags.

The existing `woobe-cli` Trusted Publisher is unchanged. The new name needs its
own first publication before npm allows configuring Trusted Publishing:

1. After approving/merging this PR, download the **same release's** skill `.tgz`
   and `SHA256SUMS` from GitHub Releases. Verify the hash with `sha256sum` on Linux,
   `shasum -a 256` on macOS or `Get-FileHash -Algorithm SHA256` in PowerShell.
2. Log in locally to your npm owner account with `npm login`. Confirm access to
   the unscoped name `woobe-cli-skill`; do not send tokens in chat.
3. Publish the already validated tarball: `npm publish ./woobe-cli-skill-VERSION.tgz
   --access public`. Complete npm's interactive 2FA as required. This one-time
   local bootstrap does not include GitHub OIDC provenance.
4. At npm → `woobe-cli-skill` → Settings → Trusted Publisher, add GitHub Actions:
   owner **A1b3rt0M3rcad0**, repository **woobe-cli**, workflow **release.yml**, no
   environment name. Allow `npm publish`; no dist-tag permission is required.
5. At GitHub repository Settings → Secrets and variables → Actions → Variables,
   create repository variable **WOOBE_SKILL_NPM_PUBLISH** with value **true**.
6. The next automatic release publishes both packages through OIDC/provenance.
   No `NPM_TOKEN` is read. Before step 5, only `npm-skill` is skipped; built-in skill installation needs none
   of these npm publisher steps. Native,
   GHCR and existing CLI npm publication continue normally. The GitHub skill
   tarball remains installable with `npx --package=./woobe-cli-skill-VERSION.tgz
   woobe-skill install --agent codex`.

To validate the new Trusted Publisher immediately, rerun `Release CLI` from
master with the released version and exact source revision. An identical existing
npm version is verified, never republished; a fresh patch release is needed to
actually exercise a first OIDC publish. Never enable the variable until the
publisher is configured. Removing the variable pauses only skill npm publication.

Recovery uses the same validated tarball/source manifest; integrity conflicts
fail rather than overwrite a version. Stable versions use `latest`, prereleases
`next`, and older recovery releases `historical` independently for each package.

## Repository validation

Contributors should follow [AGENTS.md](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/AGENTS.md).
CLI behavior changes require reviewing the corresponding help, guide and canonical
skill reference in the same PR. The native and npm distributions share one skill
payload; generated docs and compatibility checks must stay synchronized.

Run `make check` for Go/Python and installer tests, then
`bash scripts/package.sh 0.0.0-ci.1 --with-npm` and
`python3 scripts/verify_artifacts.py --commit "$(git rev-parse HEAD)"`.
`scripts/smoke_skill.py` installs the actual tarball offline and exercises the
installer/npx. `scripts/validate_skill_commands.py` checks every fenced CLI
example against the packaged binary's help, without server requests.
See the [repository documentation index](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/INDEX.md) for broader CLI workflows and limitations.

The assistant payload now requires CLI 0.32.3 or newer because its ASaC guides
include explicit structural package validation, strict read projection and verified editable package copies, in addition
to revision catalog fetch and retained executable hydration. These commands
negotiate the backend's revision catalog and hydration capabilities. CLI 0.19.1
introduced support for versioned
compiler recipes in retained author objects. Upgrade the CLI before installing
or updating this payload (`npm install -g woobe-cli@latest` or the latest
verified native release). This compatibility floor is independent of the
calculated release version; older payloads are not rewritten.

The current payload includes exact isolated Candidate preparation with Stage `--revision`, status inspection and original-acceptance reconciliation. These require CLI 0.24+ and an explicitly advertised backend capability; a ready Candidate is not Evaluation or publication evidence.

The current payload also includes versioned YAML Candidate evaluations for Agents and Networks, original write reconciliation and native Run evidence inspection (CLI 0.25+ and an advertised compatible backend). Evaluation does not publish or activate.
