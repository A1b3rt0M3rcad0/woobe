# Releasing Woobe

This document is the canonical release procedure for Woobe. It applies to the first public release and to every subsequent platform release.

A release is an immutable, reviewed state of the Woobe repository identified by a Semantic Version and a Git tag. Development continues on `master` after a release is published; published tags are never moved to follow `master`.

## Automatic publication

Merging a normal development PR into `master` starts **Release Woobe** (`prepare-release.yml`). The workflow calculates the next version, opens or resumes a narrow version-synchronization PR, waits for all eight required CI workflows on its exact HEAD, merges it and publishes the validated artifacts. Developers do not edit package versions or create release tags by hand.

The published packages are the existing GHCR images `woobe-api`, `woobe-workers`, `woobe-frontend` and `woobe-embed`, each for `linux/amd64` and `linux/arm64`. The immutable `v<VERSION>` Git tag and GitHub Release identify the same release revision; `release-manifest.json` records all four image digests. This workflow does not add npm or PyPI publication.

To retry or publish intentionally, open **Actions → Release Woobe → Run workflow**, select `master` and leave `version` empty for automatic selection/recovery. An explicit version remains available for recovery, prereleases and reviewed overrides. Publication succeeds only after the entire validation and promotion transaction succeeds.

## Publication runners

All eight required CI workflows, parent release jobs, candidate builders and publication jobs use pinned `ubuntu-24.04` GitHub-hosted runners. For public repositories, this standard Linux runner is an ephemeral x64 VM with 4 vCPUs, 16 GB RAM and 14 GB SSD; standard GitHub-hosted Actions minutes are free. While Woobe remains private, the private-repository minute quota and billing apply. Docker/Compose, Git and GitHub CLI are present on the runner image; Python, UV, QEMU and Buildx are configured or checked by pinned actions as needed.

Each hosted job owns an isolated Docker daemon. The CI Docker preflight verifies daemon access directly, without starting host-level locks or Docker socket proxies. Cleanup reclaims unused images and builder cache between Docker-heavy phases to conserve the limited runner disk. The four release-candidate image builds run concurrently on independent VMs; multi-architecture output remains `linux/amd64,linux/arm64` via QEMU/Buildx. Release jobs use private per-job `DOCKER_CONFIG` directories, and cleanup removes job-owned builders and temporary registry credentials. Compose teardown remains scoped to the job's own project.

The preparation job waits for required CI without holding Docker resources. Required checks must still pass for the exact release PR HEAD before a merge or publication can occur. Queueing is possible if GitHub-hosted capacity or private Actions quota is unavailable. See [Public repository readiness](docs/operations/PUBLIC_REPOSITORY_READINESS.md) for runner de-registration, visibility, security and GHCR requirements.

## Versioning policy

Woobe platform releases use Semantic Versioning:

```text
MAJOR.MINOR.PATCH
```

Git tags add the `v` prefix:

```text
v0.12.0
v0.12.1
v0.13.0
v1.0.0
```

Container/image versions and release workflow inputs use the version without the `v` prefix.

Before `1.0.0`, Woobe is explicitly pre-stable. The project still uses the following practical policy:

- PATCH (`0.12.0 -> 0.12.1`) for compatible fixes, security fixes and release corrections.
- MINOR (`0.12.x -> 0.13.0`) for meaningful feature releases and intentionally breaking pre-1.0 changes.
- MAJOR (`1.x -> 2.0.0`) after `1.0.0` for incompatible changes to supported public contracts.
- MINOR after `1.0.0` for backward-compatible features.
- PATCH after `1.0.0` for backward-compatible fixes.

Automatic selection reads commit subjects and bodies since the latest published platform tag, using the same Conventional Commit policy as woobe-cli:

| Commits included since the published tag | Next release |
| --- | --- |
| `feat(scope): ...` | MINOR |
| `type(scope)!: ...` or a `BREAKING CHANGE:` / `BREAKING-CHANGE:` footer | MINOR before 1.0; MAJOR from 1.0 |
| `fix`, `docs`, `ci`, `build`, `refactor`, other compatible commits | PATCH |

The highest impact wins. Normal merge commits preserve the underlying commit history; squash commits must preserve the Conventional Commit subject and breaking footer. Automatic selection produces a stable version; an explicit dispatch can select a prerelease. `VERSION` is a floor, not a reason to lower a published version.

Pre-release identifiers such as `0.2.0-rc.1` may be used when a release candidate is intentionally published. A release candidate is not the final release and must not reuse the final tag.

## Branch model

`master` is the integration branch.

Normal work continues through focused branches and pull requests:

```text
feature/*
fix/*
chore/*
docs/*
ci/*
       -> PR -> master
```

A platform release is prepared from the current reviewed `master`:

```text
master
  |
  +-- release/<VERSION>
          |
          +-- version synchronization
          +-- final validation
          |
          +-- PR -> master
                    |
                    +-- release artifacts/images
                    +-- post-publish smoke
                    +-- tag v<VERSION>
                    +-- GitHub Release
```

Example:

```bash
git checkout master
git pull origin master
git checkout -b release/0.2.0
git push -u origin release/0.2.0
```

The release branch contains only deterministic platform-version synchronization. Product fixes, changelog entries and documentation must be reviewed in normal development PRs on `master` before publication. Fix a failed gate through that reviewed path; the orchestrator refreshes the release branch and requires CI on the new HEAD.

After the release is complete, delete the release branch. The Git tag is the permanent release reference.

## 1. Select the release version

Normally the identity job selects the version automatically from reviewed `master` history and published release metadata. It prioritizes an unfinished release over reserving a new version, resumes a single existing release PR, and skips superseded push events or source revisions already included in the latest publication. A skip is reported as a skip, never as a new publication.

The identity job fails on GitHub authentication/metadata errors, ambiguous open release PRs, inconsistent tag/VERSION identity or a canonical version older than the latest publication. It never treats an API failure as an absent release.

For an intentional override, review compatibility and select a strict Semantic Version newer than published versions, or specify an existing release for immutable recovery. The first-ever release can use the explicit `allow_initial_version_rebase` exception; normal automated publication cannot lower versions.

The platform version is independent from Agent Releases, Network Releases, Skills and other domain objects that have their own version values. Values such as `v1.0.0` or `1.0.0` in Agent/Network/Skill tests, fixtures, examples and persisted-domain behavior must not be mass-replaced when the Woobe platform version changes.

Never perform a repository-wide replacement of the old platform version.

## 2. Prepare the release branch

`VERSION` at the repository root is the canonical Woobe platform version. The automatic identity job chooses the target; the release PR synchronizes this file and all release-bearing manifests, lockfile version metadata and runtime version mirrors together.

The normal release path is the **Release Woobe** GitHub Action started by a `master` push after a reviewed development merge. A manual dispatch from `master` follows the same gates.

1. Merge a reviewed development PR into `master`, or open **Actions → Release Woobe → Run workflow**.
2. Automatic selection is the default. For an override/recovery, enter the Semantic Version without `v`.
3. The workflow validates strict Semantic Version syntax, recovers existing publications idempotently, and requires new releases to advance beyond published versions and canonical `VERSION`. The optional `allow_initial_version_rebase` input exists only for an explicit first-ever published release whose chosen public version is lower than a pre-release development version.
4. If `VERSION` already equals the requested version on `master` and no GitHub Release exists, the workflow enters post-merge recovery mode instead of trying to recreate the release PR. It resolves the exact historical merge commit of the merged `release/<VERSION>` PR (or, as a fallback, the existing immutable `v<VERSION>` tag) so later `master` commits cannot silently change the release revision. Any existing `v<VERSION>` tag must point to that recovered revision.
5. Otherwise, if `release/<VERSION>` already has an open PR targeting `master`, the workflow resumes that PR without rewriting the branch or creating another PR. An unrelated/orphan branch remains blocking.
6. It runs `scripts/release/set_platform_version.py <VERSION>`, validates the synchronized state with `scripts/ci/check_package_versions.py`, creates `release/<VERSION>`, and opens the normal release PR.
7. The release gate waits for the complete required CI matrix on the exact PR HEAD. Approval-required workflow runs are waited on; failed, cancelled, skipped or timed-out required checks block the release.
8. If `master` advances while validation is running, the release branch is refreshed from current `master` and the new exact HEAD must pass CI again.
9. Only a stable release HEAD with every required gate green is merged automatically. For automatically selected versions, a final impact check rejects concurrent `master` changes requiring a higher version instead of publishing them under an insufficient bump.
10. The resulting merge commit becomes the only release revision. **Release Woobe** invokes **Release candidate images** as a reusable workflow for that exact SHA.
11. Candidate build produces API, Workers, Frontend and Embed images for both `linux/amd64` and `linux/arm64`. Existing immutable SHA candidates may be reused only after identity revalidation.
12. Candidate lookup is fail-closed: only an explicit registry not-found response permits a new build; authentication, timeout and transient registry failures abort.
13. Multi-architecture verification and production-shaped candidate smoke must pass.
14. The candidate reusable workflow returns the exact SHA256 digest for each of the four validated images plus a validation identity directly to the parent workflow. No GitHub Actions artifact is required for orchestration.
15. **Release Woobe** invokes **Publish Woobe Core images** as a reusable workflow and passes those exact digests.
16. Publication first revalidates candidate digests/platforms and then preflights all four `<VERSION>` GHCR targets before writing any one of them. Each target must be conclusively missing or already point to the expected digest; a conflicting digest or unknown/error state aborts before promotion.
17. Publication promotes the exact validated digests to the release version without rebuilding. Promotion is idempotent: an existing tag with the expected digest is preserved, while a different digest blocks the release.
18. The published images are pulled and smoke-tested again.
19. Only after post-publish smoke succeeds does the publisher create or verify the immutable Git tag `v<VERSION>` on the exact release revision. It then creates/repairs the GitHub Release, attaches the permanent `release-manifest.json`, and removes the release branch.
20. **Release Woobe reports success only after all upstream CI, candidate validation, all-target registry preflight, digest promotion, post-publish smoke, immutable Git tagging and GitHub Release creation have succeeded.** Reusable-workflow failure/cancellation propagates to the parent.

The candidate workflow keeps an optional manual `workflow_dispatch` entrypoint for diagnostics/revalidation. Publication is callable only by the parent through `workflow_call`; it cannot be started directly or by a tag push. These child workflows are not triggered by `master` or `v*` pushes; only the parent has the `master` push trigger. This removes the former race and prevents bypassing the successful candidate gate.

Release-child concurrency is serialized without cancellation. A second invocation for the same release SHA/version must wait; it must never cancel an in-progress candidate smoke or partial publication. External registry reads use bounded retries with explicit image/ref diagnostics.

For automatic PR creation and merge, enable **Settings -> Actions -> General -> Workflow permissions -> Allow GitHub Actions to create and approve pull requests**. With the default `GITHUB_TOKEN`, GitHub can place pull-request workflow runs in an approval-required state; the orchestrator waits for approval rather than treating `action_required` as test success or failure.

The default `GITHUB_TOKEN` has Actions write permission so the orchestrator can dispatch required workflows when bot-created PRs do not trigger them. Normal Actions approval rules still apply. An additional token is optional, not a prerequisite when repository permissions allow PR creation. For normal push/PR event propagation, configure the repository secret `WOOBE_RELEASE_TOKEN` with a GitHub App installation token or personal access token with Contents, Pull requests and Actions write access. The workflow uses it consistently for Git checkout/push and GitHub CLI operations.

`master` should also be protected at the GitHub repository level so direct pushes cannot bypass the PR/check contract. The release workflow performs a repository-policy preflight and emits a warning when GitHub reports `master` as unprotected. Repository protection is an account/repository setting, not something the source-controlled workflow can enable for itself.

If orchestration fails before merge, run **Release Woobe** again with an empty version (or the same explicit version) to resume the open release PR. If it fails after merge, run **Release Woobe** again with an empty version (or the same explicit version): because `master/VERSION` already matches, it resolves the exact historical release merge and resumes post-merge finalization. Existing SHA candidates and correctly promoted version tags are reused safely, while candidate smoke and final publication checks are revalidated. If the GitHub Release was actually created before the parent workflow lost its status, the retry verifies the immutable tag/revision and returns successful idempotent completion instead of attempting to publish again. Do not delete or move a valid release tag as a normal retry mechanism.

The release PR is an auditable, deterministic version-synchronization unit. Product code, migrations, changelog entries, public documentation and compatibility notes must already be reviewed on `master` through normal development pull requests before starting the release.

When no published Woobe release with a corresponding API image exists, Acceptance treats the previous-release upgrade probe as a first-release baseline and skips only that historical-upgrade check. All current-schema, package, container, security and smoke validation still runs.

Manual fallback:

```bash
VERSION=0.15.0

git checkout master
git pull --ff-only origin master
git checkout -b "release/$VERSION"
python scripts/release/set_platform_version.py "$VERSION"
python scripts/ci/check_package_versions.py
git diff --check
git add VERSION pyproject.toml uv.lock packages
git commit -m "chore(release): prepare Woobe v$VERSION"
git push -u origin "release/$VERSION"
```

Repository-authored commits must still follow `CONTRIBUTING.md`. The release PR should use the conventional title `chore(release): prepare Woobe v<VERSION>`, but the final merge commit subject is not part of release identity.

## 3. Canonical platform-version contract

The canonical platform-version source synchronized by release preparation is:

- `VERSION`

The synchronization script owns the static mirrors required by packaging and runtime surfaces.

### Python product manifests

The script synchronizes:

- `pyproject.toml`
- `packages/woobe-core/pyproject.toml`
- `packages/woobe-api/pyproject.toml`
- `packages/woobe-workers/pyproject.toml`
- exact `woobe-core==<VERSION>` dependencies in API and Workers
- the root Woobe package version recorded in `uv.lock`

### Browser/product manifests

The script synchronizes:

- `packages/woobe-runtime-client/package.json`
- `packages/woobe-ui/package.json`
- `packages/woobe-frontend/package.json`
- `packages/woobe-embed/package.json`
- the top-level and root-package version metadata in the Frontend and Embed `package-lock.json` files

Version-only release preparation must not alter third-party dependency resolution. Dependency changes require their normal package-manager lock regeneration and review.

### Runtime/version metadata

The script also synchronizes first-party runtime metadata that exposes the Woobe platform version:

- FastAPI application metadata in `packages/woobe-api/src/main.py`
- Woobe MCP client metadata in `packages/woobe-core/src/modules/agent/application/mcp_discovery.py`
- Woobe MCP OAuth/safety client metadata in `packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py`

`scripts/ci/check_package_versions.py` treats `VERSION` as authoritative and fails CI when any release-bearing mirror, exact Core dependency, lockfile version or runtime version token diverges.

Do not perform repository-wide version replacements. Agent Releases, Network Releases, Skills, protocol fixtures, migrations, examples and third-party package versions are independent from the Woobe platform version.

### Engineering-only packages

Do not automatically synchronize engineering-only package versions with the Woobe platform release.

This includes packages under `tooling/` and test-only manifests such as `tests/e2e/package.json`, unless those artifacts become independently distributed and a separate versioning policy explicitly requires it.

### Enterprise boundary

`packages/woobe-ee` is governed separately by `LICENSE_EE.md`. If Enterprise implementation becomes a separately versioned or distributed artifact, its versioning and compatibility requirements must be defined explicitly before publication. Do not assume that source visibility or co-location automatically makes an Enterprise artifact part of the Core release grant.

## 4. Update the changelog

`CHANGELOG.md` is the repository history of user-visible platform changes.

Maintain operator-facing entries under `## Unreleased` in development PRs, including migration and compatibility implications. The version-synchronization PR intentionally does not edit changelog prose. GitHub Release notes are generated from reviewed PR history and preserve author attribution and the previous-tag comparison.

If a versioned changelog section is needed, prepare it through a normal documentation PR rather than adding unrelated prose to the automated release PR. Keep historical version sections intact; do not use the changelog as an alternative version-selection source.

Example:

```markdown
## Unreleased

## [0.2.0] - 2026-10-15

### Added
- ...

### Changed
- ...

### Fixed
- ...

### Security
- ...
```

Do not use the changelog as a raw commit log.

## 5. Review public documentation and compatibility

Every release must review documentation affected by the release, even when no documentation change is ultimately required.

At minimum review:

- `README.md`
- `docs/SELF_HOSTING.md`
- `docs/UPGRADING.md`
- `SECURITY.md`
- `docs/ARCHITECTURE.md`
- relevant runtime/API documentation under `docs/`
- `.env.example`
- root `compose.yaml`

If configuration keys, ports, services, persistence behavior, migrations, public APIs, authentication, runtime contracts or deployment topology changed, update the corresponding documentation in the release branch.

If a release requires operator action, `docs/UPGRADING.md` and the GitHub Release notes must state it explicitly.

Do not claim compatibility that has not been validated.

## 6. Database and persisted-state review

For every release, determine whether the release changes persisted state.

If PostgreSQL schema changes are present:

- confirm the Alembic migration exists under `packages/woobe-core/migrations/versions/`;
- verify upgrade from the previous supported release to the new release;
- verify a fresh installation reaches the same schema;
- document any irreversible or operationally significant migration;
- do not assume application rollback makes a database downgrade safe.

If MongoDB, Redis, Knowledge storage or persisted Run semantics changed, document and validate the compatibility path separately.

Release notes must identify backup requirements when an upgrade can materially transform persisted data.

## 7. Validate repository and distribution boundaries

Before publication, confirm the release tree still represents the intended Woobe product.

The release must satisfy all of the following:

- root `compose.yaml` remains the supported default Woobe Core self-host contract;
- `compose.test.yaml` remains validation infrastructure, not a product deployment contract;
- development-only infrastructure remains explicit;
- Core package boundaries match `LICENSE.md`;
- Enterprise material remains governed by `LICENSE_EE.md`;
- Core remains runnable without unauthorized Enterprise Production Use;
- legacy source surfaces that have been intentionally removed are not reintroduced;
- documentation reflects the package topology that actually exists.

## 8. Secrets and Git-history gate

For any release that makes repository history or refs newly public, and whenever publication scope changes, audit Git history rather than only the working tree.

Run:

```bash
scripts/audit_public_history.sh
```

Review findings manually.

Deleting a credential or proprietary file in a later commit does not remove it from Git history. Real credentials found in history must be rotated or revoked. Separately licensed or proprietary material must not become public merely because it is absent from current `HEAD`.

For the first public release, this gate is mandatory against the exact refs intended for publication.

## 9. Licensing, brand and third-party gate

Before releasing source or compiled artifacts, review:

- `LICENSE.md`
- `LICENSE_EE.md`
- `LICENSING.md`
- `CONTRIBUTOR_LICENSE_AGREEMENT.md`
- `TRADEMARKS.md`
- `NOTICE.md`
- `THIRD_PARTY_NOTICES.md`

The release must preserve the intended Core/Enterprise boundary, Woobe brand policy, attribution and third-party obligations.

For distributed artifacts:

- generate SPDX SBOMs for the exact release images;
- review the generated third-party inventory against the actual component licenses;
- preserve required copyright and attribution notices;
- include required license copies, source offers or other distribution obligations;
- confirm `NOTICE.md` and `THIRD_PARTY_NOTICES.md` correspond to the artifacts actually being distributed.

The current Core container quality workflow covers the Core API, Web and ChatSurface build targets. Enterprise or additional artifacts require their own inventory coverage when not represented by that workflow.

Legal review requirements recorded in this repository are release gates, not assertions that automated tooling constitutes legal certification.

## 10. Run the release validation suite

A release must be validated from the release branch after all version and documentation changes are present.

### Backend and repository contract

Validate the test topology:

```bash
docker compose -f compose.test.yaml config --quiet
```

Run the backend/repository validation contract:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

Clean it after validation:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

### Core deployment

Generate a fresh self-host environment:

```bash
python scripts/generate_self_host_env.py
docker compose config --quiet
docker compose up -d --build
```

Verify the complete supported Core stack, including:

- PostgreSQL
- MongoDB
- RabbitMQ
- Redis
- migrations
- API readiness
- Workers
- Web
- ChatSurface
- first-owner/bootstrap behavior
- representative Agent execution
- representative Agent Network execution
- Sessions/Runs/Traces
- Knowledge access
- Run journal persistence from Redis to MongoDB

Also exercise production-shaped security configuration: secure cookies, exact HTTPS origins, trusted hosts and independent strong secrets.

### Frontend and browser artifacts

Run the package-specific test/build commands for every browser artifact changed by the release.

At minimum:

```bash
cd packages/woobe-frontend
npm ci
npm run test:run
npm run build
```

And:

```bash
cd packages/woobe-embed
npm ci
npm test
npm run typecheck
npm run build
```

For `packages/woobe-runtime-client`:

```bash
cd packages/woobe-runtime-client
npm run typecheck
```

Run any additional package, architecture, E2E, acceptance, security and container workflows required by repository rules.

### Container/release artifact validation

Validate package artifacts before container publication:

- `woobe-core`, `woobe-api` and `woobe-workers` build wheel and source distributions;
- clean environments can install the exact local Core + API and Core + Workers artifacts without source-tree path coupling;
- Frontend and Embed produce production bundles from clean dependency installs;
- all release-bearing package manifests agree on the platform version.

The per-PR `Package Build` workflow enforces this contract continuously.

Optional short-lived CI evidence uploads are disabled by default so GitHub Actions artifact quota cannot block or noisily degrade the normal validation path. Set repository variable `WOOBE_UPLOAD_CI_ARTIFACTS=true` only when those diagnostic artifacts are explicitly needed. Release correctness does not depend on Actions artifact storage; the final release manifest is attached to the GitHub Release itself.

Validate the exact images intended for publication:

- successful multi-architecture build where supported;
- smoke the prebuilt API, Workers, Frontend and Embed images without allowing Compose to rebuild them;
- validate schema upgrade from the most recent release tag reachable from the target branch to the PR schema while preserving a persisted-state probe;
- non-root execution;
- OCI license metadata;
- SBOM generation;
- third-party inventory;
- HIGH/CRITICAL vulnerability scanning according to repository policy;
- startup/readiness;
- representative production-shaped smoke tests.

Do not publish a different commit from the one that passed final release validation.

## 11. Prepare the release pull request

The automated preparation workflow opens:

```text
release/<VERSION> -> master
```

with the canonical pull request title:

```text
chore(release): prepare Woobe v<VERSION>
```

A release PR is intentionally narrow. It may contain only the deterministic files owned by platform-version synchronization. The release orchestrator rejects unexpected file paths before merge.

The required release gates are:

- Backend test suite;
- Frontend test and build;
- Package Build;
- Acceptance;
- Quality Gate;
- Container quality;
- Security audit;
- CLA acceptance.

Only `success` satisfies a required gate. Runs must match the required workflow file and exact HEAD; all result pages are inspected and the newest run ID wins, including runs created in the same second. Older cancelled runs do not override a newer run for the same workflow and exact HEAD. Missing workflows are explicitly dispatched as a fallback. Approval-required runs already exist and must be approved through GitHub; they are never redispatched to avoid that approval.

The orchestrator also requires the validated PR HEAD to include current `master`. If `master` advances, the release branch is refreshed and the new HEAD must pass the complete gate again.

A failed gate leaves the PR open for diagnosis and posts a release-blocked comment. No merge, Git tag, container promotion or GitHub Release occurs.

## 12. Merge and automatic release finalization

The release orchestrator merges the exact validated PR HEAD using the repository merge strategy only after all required release gates pass. The merge operation is pinned to the validated head SHA so a concurrent PR update cannot be merged without another CI pass.

After merge, **Release Woobe remains the owner of the transaction**. It invokes the candidate and publication workflows as reusable workflows with `workflow_call`; it does not poll independent child runs and does not depend on tag-push side effects.

The exact merge commit becomes the immutable release revision. Candidate processing:

1. validates canonical `VERSION` and every release-bearing mirror on that exact SHA;
2. probes each `sha-<commit>` GHCR candidate fail-closed;
3. treats only an explicit registry not-found response as permission to build;
4. retries transient registry/authentication failures and aborts rather than overwriting an uncertain candidate;
5. builds API, Workers, Frontend and Embed for `linux/amd64` and `linux/arm64`;
6. validates OCI revision/version identity for existing or newly built candidates;
7. verifies both release architectures;
8. smoke-tests those exact candidate images;
9. resolves the exact SHA256 manifest-list digest for each image;
10. exposes those digests directly to the parent reusable-workflow call.

No GitHub Actions artifact is required to transport release state between candidate validation and publication.

A failure before post-publish smoke completes does not create a new release tag. Re-running **Release Woobe** with the same version after a post-merge failure recovers the exact historical merge revision and revalidates the candidate.

## 13. Container publication and immutable tag

After candidate validation succeeds, **Release Woobe** invokes the publisher without requiring a Git tag to exist first. Tag creation is not a publication trigger. `.github/workflows/release.yml` has no `push: tags` release path; normal publication is invoked explicitly by the parent as a reusable workflow.

Publication receives:

- exact platform version;
- exact release revision;
- candidate validation identity;
- API digest;
- Workers digest;
- Frontend digest;
- Embed digest.

Before promotion, publication re-inspects each `sha-<commit>` candidate and requires its registry digest and both architectures to match the candidate outputs.

It then performs an all-target preflight over API, Workers, Frontend and Embed before promoting any image. For an existing `<VERSION>` image tag, registry lookup has three states:

- **exists** — its digest must equal the validated candidate digest;
- **not found** — promotion is allowed;
- **unknown/error** — publication aborts without writing anything.

This distinction prevents a timeout, authentication failure or transient registry outage from being misinterpreted as permission to overwrite a supposedly missing tag.

Promotion never rebuilds the release:

```text
exact release commit
        ↓
validated multi-arch sha-<commit> candidates
        ↓
exact SHA256 digest outputs
        ↓
all-target GHCR preflight
        ↓
digest-preserving GHCR promotion
        ↓
<VERSION> image tags
        ↓
post-publish smoke
        ↓
v<VERSION> immutable Git tag
```

Partial promotion is recoverable. A retry preserves any version tag already pointing to the expected digest and continues with missing units. Because all four destinations are preflighted before the first write, known conflicts are detected before promotion starts. A conflicting digest permanently blocks reuse of that version and is never overwritten automatically.

## 14. Post-publish verification and permanent manifest

After promotion, the workflow pulls all four registry-delivered `<VERSION>` images, verifies their embedded revision/version labels and runs the production-shaped smoke contract again.

Only after that smoke succeeds does the workflow create or verify the immutable Git tag on the exact release revision and then create the GitHub Release.

A permanent `release-manifest.json` is attached to the GitHub Release. It records:

- schema version;
- Woobe version;
- exact Git revision;
- candidate validation identity;
- repository;
- supported platforms;
- exact SHA256 digest of API;
- exact SHA256 digest of Workers;
- exact SHA256 digest of Frontend;
- exact SHA256 digest of Embed.

The release manifest is part of the permanent release record rather than a temporary GitHub Actions artifact. If a retry finds an existing manifest asset, its contents must match the expected release state exactly.

After the GitHub Release is confirmed, the workflow removes `release/<VERSION>` when that branch still exists.

## 15. Developer workflow and recovery

A developer writes Conventional Commits, adds meaningful tests and operator documentation, opens a normal PR, waits for CI and merges it into `master`. That merge starts automatic release preparation. Do not manually bump platform manifests, push tags or merge a release PR ahead of the orchestrator. Watch **Actions → Release Woobe** for the complete result.

An explicit manual dispatch remains available for recovery or a reviewed version override. Both triggers publish only if every technical gate succeeds.

The parent workflow is composed as:

```text
Reviewed master push or optional manual dispatch
  ↓
automatic version selection / recovery / intentional skip
  ↓
prepare/release PR + required CI + exact merge
  ↓
reusable Release candidate images
  ↓
reusable Publish Woobe Core images
  ↓
all-target GHCR preflight + digest promotion
  ↓
post-publish smoke
  ↓
immutable Git tag
  ↓
GitHub Release + permanent release-manifest.json
  ↓
release branch cleanup
```

Failure or cancellation propagates through the reusable workflow chain; there is no separate polling process that can silently lose the child status.

Recovery rules:

- **Before merge:** run **Release Woobe** again with an empty version or the same explicit version to resume the open release PR.
- **After merge but before GitHub Release:** run **Release Woobe** again with an empty version or the same explicit version. It resolves the historical merge commit of `release/<VERSION>`, reuses only candidates whose identity is valid, and resumes finalization.
- **After GitHub Release exists:** if `release-manifest.json` is present, a retry verifies the immutable tag, manifest, all four versioned registry digests, architectures and OCI labels, and completes pending release-branch cleanup. If the GitHub Release exists but the permanent manifest is missing, the release is treated as incomplete and normal candidate/publication finalization resumes to repair the release record.
- **Concurrent higher-impact work:** automatic coverage validation blocks an insufficient release target before merge. Inspect the open release PR, close the obsolete PR and remove its unmerged release branch before retrying automatic calculation, or select a reviewed higher explicit target after resolving the obsolete branch. Do not bypass the CI gate or move existing tags.
- **New work during post-merge recovery:** finish the original immutable revision first. After recovery succeeds, dispatch with an empty version to publish remaining `master` changes. A queued newest push can also start that next transaction. The workflow serializes releases without cancellation and may batch multiple development merges into one release.
- Manual `release-candidate.yml` remains available for candidate diagnostics/revalidation.
- `release.yml` has no manual dispatch entrypoint; publication authority comes only from the successful parent/candidate reusable-workflow chain.
- Never move/reuse a published Git tag or overwrite a versioned GHCR image with different bytes.

Current Core release units are:

- `woobe-core==<VERSION>` — Python domain/runtime package used by backend process images;
- `woobe-api:<VERSION>` — independently deployable API container;
- `woobe-workers:<VERSION>` — independently deployable background-execution container;
- `woobe-frontend:<VERSION>` — independently deployable administrative Web container;
- `woobe-embed:<VERSION>` — independently deployable ChatSurface container.

The release workflow promotes the four container units. Core is not published as a standalone container because it is a library/migration boundary rather than a process host.

## 16. Post-release verification

After publication, the release workflow already pulls the versioned images back from GHCR and smoke-tests those exact registry artifacts. Complete the remaining release verification:

1. Confirm the post-publish smoke job succeeded and candidate/version image digests matched during promotion.
2. Start or inspect a clean installation using the published artifacts.
3. Verify the reported platform version where exposed.
4. Verify API readiness and core UI access.
5. Execute representative Agent and Network Runs.
6. Verify persistence and observability.
7. Verify upgrade instructions from the previous supported release when applicable.
8. Verify GitHub Release, Git tag and published image tags all identify the same version.
9. Record any release defect as a fix for a new version; do not mutate the published tag.

## 17. Close the release branch

After publication and post-release verification:

```bash
git branch -d "release/$VERSION"
git push origin --delete "release/$VERSION"
```

Development continues normally through pull requests to `master`.

The released version remains permanently identified by its Git tag even as `master` advances.

## Hotfix and patch releases

A defect in a published release is fixed by a new release. Do not modify the old tag.

For a normal patch release:

```text
master
  -> fix/*
  -> master
  -> release/X.Y.(Z+1)
  -> master
  -> vX.Y.(Z+1)
```

If `master` contains changes that must not ship in the patch, create the patch branch from the affected release tag, apply only the required fix, and then reconcile that fix back into `master`. Document this exception in the release PR.

## Release invariants

Every Woobe release must satisfy these invariants:

1. Root `VERSION` is the canonical Semantic Version for the platform release.
2. All release-bearing product manifests and runtime version mirrors agree with canonical `VERSION`.
3. Generated lockfile version metadata agrees with canonical `VERSION` and its source manifests.
4. Operator-facing changelog entries and attributed GitHub Release notes describe the reviewed changes.
5. Required migrations and upgrade notes are present.
6. The exact release commit passed the required validation.
7. The Git tag points to that exact release commit.
8. GitHub Release and published artifacts use that same version.
9. Published immutable tags are never moved or reused.
10. `master` may continue advancing immediately after release without changing any previously published version.
11. Agent, Network, Skill and other domain-object versions are not conflated with the Woobe platform version.
12. Licensing, Enterprise boundaries, brand policy and third-party obligations are reviewed for the actual artifacts being distributed.
13. The GitHub Release preserves PR-to-author attribution for changes included in the release.
14. First-time human contributors are acknowledged when applicable.
15. The Full Changelog comparison uses the previous published platform tag, or the explicitly recorded baseline for the first public release.
16. The canonical release commit produced a successful immutable `sha-<commit>` candidate for all four container units before tagging.
17. Versioned container tags are digest-preserving promotions of those tested candidates, not rebuilds.
18. The registry-delivered versioned images passed post-publish smoke validation.
19. The GitHub Release contains `release-manifest.json` with the exact release revision and four published multi-arch image digests.
20. A publishing `Release Woobe` run succeeds only when the complete reusable-workflow transaction reaches its verified terminal state; intentional no-op runs explicitly report their skip reason.
