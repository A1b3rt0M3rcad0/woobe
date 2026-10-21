# Installation and automatic CLI releases

The CLI stays in this repository and is versioned independently of the Woobe
backend. Distribution uses **GitHub Releases** and **GitHub Packages (GHCR)**: six native archives for Linux,
macOS and Windows, in amd64/x64 and arm64. Go, Node.js and npm are not required
to use the binaries. The same release also publishes `woobe-cli` to npm, with all
six executables bundled and no installation scripts or external binary downloads.
The npm launcher requires Node.js 22 or newer.

The initial release floor is **0.1.0**. Publication requires the complete CI
gate. Master pushes calculate the next version automatically; an explicit
`v<VERSION>` tag also releases its exact source without requiring a merge.

## Download and run

Open [the latest release](https://github.com/A1b3rt0M3rcad0/woobe-cli/releases/latest)
and download your platform archive plus `SHA256SUMS`.

| Platform | Example archive |
| --- | --- |
| Linux x64 | `woobe_0.13.7_linux_amd64.tar.gz` |
| Linux arm64 | `woobe_0.13.7_linux_arm64.tar.gz` |
| macOS Intel | `woobe_0.13.7_darwin_amd64.tar.gz` |
| macOS Apple Silicon | `woobe_0.13.7_darwin_arm64.tar.gz` |
| Windows x64 | `woobe_0.13.7_windows_amd64.zip` |
| Windows arm64 | `woobe_0.13.7_windows_arm64.zip` |

Verify the downloaded file's SHA-256 against `SHA256SUMS` before extraction.
Use `sha256sum` on Linux, `shasum -a 256` on macOS or
`Get-FileHash -Algorithm SHA256` in PowerShell. Extract, place `woobe` or
`woobe.exe` in a directory on `PATH`, then run:

```sh
woobe version
woobe help
```

The archives also contain usage instructions, both manifest schemas and pinned
dependency/toolchain license notices. No administrator privileges are required.

## Connect Woobe

Create a Control Key at **Workspace settings → CLI Keys**.

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

## Automatic release

**Every push to `master` starts Release CLI**, including a maintainer's merge of
a reviewed PR. No manual version update, tag push or release button
is required. npm needs the one-time publisher setup described below. The workflow never merges PRs and
never pushes changes into `master`.

1. Pin the source to the push's exact SHA, require it to belong to `master`,
   and calculate the version from existing immutable `v*` tags and commit history.
2. Run the full reusable CI: Go/race/fuzz checks, six cross-builds, archive/schema/
   license/checksum validation, and native binary plus both npm package install/launcher smoke
   tests on Linux/macOS/Windows. The npm tarball contains identical binary bytes.
3. Download the immutable Actions artifact ID and verify its manifest SHA-256.
   Extract the tested Linux binaries into a non-root, multi-platform GHCR image
   for `linux/amd64` and `linux/arm64`, without rebuilding the executables.
   Verify its digest, platforms and CLI behavior before publication.
4. Preflight both destinations and refuse conflicting tags, assets or image
   digests. Reserve `v<VERSION>` on the exact validated source, promote the image
   to `<VERSION>`, and create or resume a draft GitHub Release. Upload only
   missing files; existing bytes are never overwritten.
5. Download and compare every asset, execute the native CLI again, publish the
   Release and verify all six archives, checksums, artifacts.json and
   release-manifest.json. The permanent manifest records the package digest.
   Promote the verified stable image to `latest`; older recovery cannot move
   either destination's latest version backwards.
6. Publish the exact tested npm tarball with provenance using GitHub Actions OIDC.
   Compare the registry SHA-512 integrity with the local tarball. An identical
   retry succeeds without republishing; conflicting bytes fail. Stable versions
   use `latest`, prereleases use `next`, and older recovery uses `historical`
   without moving npm `latest` backwards. The separate `npm-skill` job publishes
   `woobe-cli-skill` only when `WOOBE_SKILL_NPM_PUBLISH=true`; the initial owner
   bootstrap is described in [AGENT_SKILL.md](AGENT_SKILL.md#versioning-and-initial-npm-publication-owner-once).

The workflow uses the built-in **GITHUB_TOKEN** with job permissions
`contents: write` and `packages: write`. No additional token is required for GitHub/GHCR. npm authorization is configured
separately below. Repository policies must allow these permissions and tag creation.
Explicit owner-created version tags trigger the same gates. Tags created by the
workflow's GITHUB_TOKEN do not trigger another workflow run.

### GitHub Packages

The repository package is `ghcr.io/a1b3rt0m3rcad0/woobe-cli`. After publication:

```sh
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:0.13.7 version
docker run --rm ghcr.io/a1b3rt0m3rcad0/woobe-cli:latest help
```

Use a volume at `/data` to persist credentials and contexts. The image runs as
UID 10001, so the directory must be writable by that UID. Package visibility is
a GitHub setting: new GHCR packages may start private even for public repositories.
The owner can change visibility in the package settings; private pulls require
GitHub authentication. Native release downloads are public independently.

### Automatic version calculation

`VERSION` is the reviewed **minimum release version**, initially `0.1.0`.
Both private npm source manifests mirror this floor. Packaging removes `private`
only from the staged distribution and sets the calculated release version.
Published versions are authoritative in Git tags and permanent artifact
manifests; automatic increments do not rewrite source files.

- No previous version: use `VERSION`.
- A `feat:` or `feat(scope):` commit since the latest tag: increment MINOR.
- A conventional `type!:` / `type(scope)!:` subject or `BREAKING CHANGE:` /
  `BREAKING-CHANGE:` footer: increment MAJOR; before 1.0, increment MINOR.
- Other changes: increment PATCH. A previous prerelease becomes its stable core
  version when no feature/breaking bump is needed.
- If a reviewed increase in `VERSION` is higher than the calculated version,
  use that floor. No source version edit is needed for ordinary releases.

Examples: `0.1.0` + `fix(cli): ...` → `0.1.1`; `feat(cli): ...` → `0.2.0`;
`1.2.3` + `fix(api)!: ...` → `2.0.0`.

### Retries and manual recovery

Release transactions are serialized and active publication is not cancelled by
later pushes. A rerun for an already tagged source recovers the same version,
even when master has advanced. A pending push superseded by a newer tagged
source is skipped. Tags reserved by a failed upload are never reused for a
later commit; the next push advances the version.

To publish an explicitly selected source without merging, create and push an
annotated `v<VERSION>` tag pointing to it. The tag must match the selected source
and version floor. Never move or reuse an existing tag.

For recovery or an explicit prerelease, **Actions → Release CLI → Run workflow**
remains available on `master`. Leave both fields empty to release its current
source automatically. To repair a specific release, enter its existing version
without `v`; its tag recovers the source. An optional full `revision` can pin the
original SHA. New explicit versions must advance all reserved versions and
respect the source floor. Every recovery still passes the complete CI gate.

Archive timestamps, owners and compression metadata are normalized. Rebuilding
the same source/version with pinned toolchains yields the same bytes. A
conflicting tag or asset is never overwritten; use a new version instead.

## Local build

```sh
make build
bin/woobe version
make package
python3 scripts/verify_artifacts.py --commit "$(git rev-parse HEAD)"
python3 scripts/smoke_artifacts.py --commit "$(git rev-parse HEAD)" --report native-smoke.json
```

Requires the Go toolchain in `go.mod`, Python 3, GNU tar, gzip, zip and sha256sum.
`make build` and `make package` use the source floor locally. Release CI passes
its automatically calculated version into packaging and embeds that version and
the exact source SHA in every binary. A bare `go build` keeps the `dev` version.
Development PR/branch packages use `0.0.0-ci.<run>.<attempt>` and are Actions
artifacts, not public releases.

For a local npm candidate, install Node.js 22+ and npm, then run:

```sh
bash scripts/package.sh 0.13.7 --with-npm
python3 scripts/verify_artifacts.py --commit "$(git rev-parse HEAD)"
python3 scripts/smoke_npm.py --commit "$(git rev-parse HEAD)" --report npm-smoke.json
python3 scripts/smoke_skill.py --commit "$(git rev-parse HEAD)" --report skill-smoke.json
```

Use your actual release version instead of the example. The repository currently
supplies no software license file; packaging adds dependency notices without
introducing a software license grant.


## npm publisher setup (owner, once)

The publishing job runs only in `release.yml`, after all CI gates and the GitHub
Release/GHCR publication succeed. Pull requests build and install the tarball
but never publish or request npm credentials. The OIDC job uses a GitHub-hosted
Ubuntu runner, Node.js 24 and npm 11.5.1, with `id-token: write`. No GitHub
environment is configured for this job.

### Existing package and authentication

`woobe-cli` has already completed its initial publication. Release CLI now requires
Trusted Publishing exclusively: it does not read `secrets.NPM_TOKEN`, and clears
`NODE_AUTH_TOKEN` in the publication step. A leftover repository token cannot
silently mask an invalid OIDC connection. No registry token is generated by
setup-node. Configure the trusted publisher before the next release.

For a fresh package in a different repository, bootstrap the first version
manually with `npm login` and `npm publish ./dist/woobe-cli-VERSION.tgz --access
public`, then configure its trusted publisher before using the release workflow.

### Switch to token-free Trusted Publishing

On npm, open **woobe-cli → Settings → Trusted Publisher → GitHub Actions**:

| Setting | Value |
| --- | --- |
| Organization or user | `A1b3rt0M3rcad0` |
| Repository | `woobe-cli` |
| Workflow filename | `release.yml` |
| Environment | Leave empty |

Save the publisher, delete the GitHub `NPM_TOKEN` secret and revoke the bootstrap
token in npm. The workflow uses OIDC exclusively, without a permanent npm token. The npm
account must own the package or have publishing permission; GitHub access alone
does not grant npm ownership.

### Recovery after an npm publication failure

The GitHub release may already be public when npm fails. Do not edit its assets,
move its tag or choose a new source for the same version. Fix the npm publisher
configuration and open **Actions → Release CLI → Run workflow**, selecting
**master** and entering the failed release's exact **version** (without `v`) and
**revision** (full commit SHA). This revalidates/rebuilds the same source and
reuses the immutable GitHub/GHCR release before retrying npm. A conflicting npm
tarball is refused. Automatic master runs may skip an already released source,
so explicit version/revision inputs are required for this recovery.

Once configured, merge reviewed changes to master for a new automatic release.
No manual npm login, version-file edit or tag creation is required. Install with:

```sh
npm install --global woobe-cli
npx --yes --package=woobe-cli woobe version
```


## Integrated project setup

Run `woobe init --agents codex`, `--agents codex-legacy` or `--agents claude`
from the project root. This prepares local development, embedded skills,
`AGENTS.md`/host instructions and `.woobe-lab`/private-state Git exclusions.
Use `--dry-run` to preview; repeat safely to add an assistant without replacing
registry identity or resource mappings. See [project setup](PROJECT_SETUP.md).

## Assistant skill installation

The CLI binary embeds the reviewed skill. No extra package, Node.js, npm,
network access or backend login is needed:

```sh
woobe skill install --agent codex
woobe skill install --agent claude
woobe skill status --agent codex,claude
woobe skill install --agent codex-legacy --scope user
```

Use `--project-dir` for an existing local directory, `--path` for a custom skills
root and `--dry-run` to preview. Updating the CLI and re-running install updates
unchanged managed skills. Native and npm installers recognize the same receipts.
Runtime Skills inside Woobe still use `project skill` operations.

### Optional independent npm package

`woobe-cli-skill` is packaged beside the native client at the same release
version/source SHA. It has no binary dependencies or npm lifecycle scripts.
Its tarball is always included in a post-merge GitHub release, even while its
npm publication is disabled pending first-publication setup. Install from npm
or directly from the verified release tarball. Installation is explicit and
supports Windows, macOS and Linux.

```sh
npx --yes --package=woobe-cli-skill woobe-skill install --agent codex,claude
npx --yes --package=woobe-cli-skill woobe-skill status --agent codex --json
```

The full [assistant guide](AGENT_SKILL.md) documents `.agents/skills`, explicit
`.codex/skills`, user scope, custom paths, updates, uninstall and the separate
Trusted Publisher. Existing `woobe-cli` publication remains independent.
Local `make check` now also requires Node.js 22+ for installer regression tests;
release builds pin Node 24 and npm 11.5.1.

The current assistant skill's ASaC examples require CLI 0.27.0 or newer.
Use the latest verified CLI release before updating the skill; historical
installation examples above remain available for pinned older versions.

## Registry processing after CI publication

npm can accept a package before exposing its public version. The release job
polls its exact integrity for up to fifteen minutes; the twenty-minute job budget
includes setup and upload. Processing is not reported as published. The polling
step never republishes a package. After a processing timeout, wait for the version
to appear, then retry the failed npm job: matching bytes are verified without a
second publication. Native GitHub assets remain available independently.
