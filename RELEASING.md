# Releasing Woobe

This document is the canonical release procedure for Woobe. It applies to the first public release and to every subsequent platform release.

A release is an immutable, reviewed state of the Woobe repository identified by a Semantic Version and a Git tag. Development continues on `master` after a release is published; published tags are never moved to follow `master`.

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
          +-- changelog and release notes
          +-- release-only fixes
          +-- final validation
          |
          +-- PR -> master
                    |
                    +-- tag v<VERSION>
                    +-- GitHub Release
                    +-- release artifacts/images
```

Example:

```bash
git checkout master
git pull origin master
git checkout -b release/0.2.0
git push -u origin release/0.2.0
```

Do not add unrelated features to a release branch. Once a release branch exists, only release preparation, blockers, documentation required by the release and fixes necessary to pass the release gates belong there.

After the release is complete, delete the release branch. The Git tag is the permanent release reference.

## 1. Select the release version

Determine the next version from the user-visible and compatibility impact since the previous platform release.

Before creating the release branch:

1. Confirm the previous published tag.
2. Review everything merged to `master` since that tag.
3. Identify public API, runtime, configuration, migration and deployment compatibility changes.
4. Select the new Semantic Version.
5. Confirm that no existing tag already uses that version.

The platform version is independent from Agent Releases, Network Releases, Skills and other domain objects that have their own version values. Values such as `v1.0.0` or `1.0.0` in Agent/Network/Skill tests, fixtures, examples and persisted-domain behavior must not be mass-replaced when the Woobe platform version changes.

Never perform a repository-wide replacement of the old platform version.

## 2. Prepare the release branch

`VERSION` at the repository root is the canonical Woobe platform version. Humans choose the target version once; release-bearing manifests, lockfile version metadata and runtime version mirrors are synchronized from that value.

The preferred release path is the **Release Woobe** GitHub Action. Starting this workflow is the human authorization to release the requested version if, and only if, the repository's release gates pass.

1. Open **Actions -> Release Woobe**.
2. Enter the target Semantic Version without the `v` prefix.
3. The workflow validates the version, requires it to be newer than the latest published Semantic Version when published tags exist, and rejects an existing `v<VERSION>`. If `release/<VERSION>` already has an open PR targeting `master`, it resumes that PR without rewriting the branch or creating another PR. An existing branch without such a PR remains blocking.
4. It runs `scripts/release/set_platform_version.py <VERSION>`.
5. It validates the synchronized state with `scripts/ci/check_package_versions.py`.
6. It creates `release/<VERSION>`, commits the synchronized release state and opens a normal release pull request.
7. It waits for the complete required CI matrix on the exact PR HEAD.
8. If GitHub requires approval to start CI, the orchestrator comments the required action on the PR and waits within its CI timeout. Once approved, it continues watching the same HEAD. A failed, cancelled, skipped or timed-out workflow blocks the release; nothing is tagged or published.
9. If `master` advances while validation is running, the workflow refreshes the release branch from current `master` and requires CI to pass again.
10. Only a stable release HEAD with every required gate green is merged automatically.
11. The exact merge commit is then handed to release-candidate finalization.

For automatic PR creation and merge, enable **Settings -> Actions -> General -> Workflow permissions -> Allow GitHub Actions to create and approve pull requests**. With the default `GITHUB_TOKEN`, GitHub creates pull-request workflow runs in an approval-required state: a maintainer must select **Approve workflows to run** on the release PR. This approval is separate from permission to create PRs; the orchestrator waits for it rather than treating `action_required` as a test failure or bypassing it with another dispatch.

For CI that starts without this additional approval, configure the already supported repository secret `WOOBE_RELEASE_TOKEN` with a GitHub App installation token or personal access token with Contents, Pull requests and Actions write access. The workflow uses it consistently for Git checkout/push and GitHub CLI operations. See [GitHub's token-trigger behavior](https://docs.github.com/en/actions/concepts/security/github_token#when-github_token-triggers-workflow-runs).

If orchestration times out before approval or stops before merge, start **Release Woobe** again from `master` with the same version to resume the existing open release PR. Retry actual failed CI runs after correcting their cause; resuming never treats a failed check as successful.

The release PR is an auditable, deterministic version-synchronization unit. Product code, migrations, changelog entries, public documentation and compatibility notes must already be reviewed on `master` through normal development pull requests before starting the release.

When no published Woobe tag with a corresponding API image exists, Acceptance treats the previous-release upgrade probe as a first-release baseline and skips only that historical-upgrade check. All current-schema, package, container, security and smoke validation still runs.

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

The only human-edited platform-version source is:

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

For a release:

1. Move relevant entries from `## Unreleased` into a new version section.
2. Use the final version and release date.
3. Keep only changes that matter to operators, integrators or users.
4. Document migration or compatibility implications when applicable.
5. Recreate an empty `## Unreleased` section for future work.

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

The release orchestrator merges the exact validated PR HEAD using the repository merge strategy only after all release gates pass. The merge operation is pinned to the validated head SHA so a concurrent PR update cannot be merged without another CI pass. Release correctness does not depend on the merge commit subject.

The canonical platform release commit is the exact `master` commit that introduces the transition of root `VERSION` from the previous platform version to `<VERSION>`.

After the automated merge, the orchestrator explicitly dispatches `.github/workflows/release-candidate.yml` for the exact merge commit with the expected platform version and release-finalization authorization. A normal `master` push that changes `VERSION` remains supported as a compatibility path. Candidate processing:

1. compares `VERSION` with the first parent;
2. validates every release-bearing mirror against canonical `VERSION`;
3. records the exact Git revision;
4. builds the four multi-architecture application images once;
5. publishes immutable `sha-<commit>` candidate tags with provenance/SBOM attestations;
6. verifies amd64 and arm64 manifests;
7. smoke-tests those exact candidate images;
8. creates the immutable annotated `v<VERSION>` Git tag on that exact validated revision;
9. dispatches `.github/workflows/release.yml` against that tag.

The initial repository introduction of `VERSION` is treated as bootstrap and does not create a release candidate.

A failed candidate does not create the release tag. Fix the release through a new reviewed commit/version rather than moving an existing tag.

Before creating the Git tag, candidate finalization also checks whether any GHCR `<VERSION>` image tag already exists. An existing version is accepted only when every existing version tag resolves to the exact validated candidate digest. A different digest blocks finalization before the Git tag is created.

For controlled recovery or revalidation, `release-candidate.yml` also accepts a manual `ref` input. Manual candidate generation validates/builds the candidate but does not automatically create a release tag or publish a release.

## 13. Immutable tag and container publication

The release tag is normally created by the successful candidate workflow. Manual tag creation is a recovery operation only.

`.github/workflows/release.yml` is automatically dispatched against the exact tag by the candidate finalization job. It also listens for direct `v*` tag pushes, so a manually created recovery tag follows the same publication contract.

The publication workflow:

1. requires an immutable `v<VERSION>` tag;
2. requires tag name == canonical root `VERSION`;
3. validates every release-bearing version mirror;
4. verifies the tag resolves to the exact checked-out revision;
5. verifies all four immutable `sha-<commit>` candidates;
6. promotes those exact OCI manifests to `<VERSION>` without rebuilding;
7. refuses to overwrite an existing version tag when its digest differs;
8. allows idempotent recovery when an existing version tag already resolves to the expected digest;
9. pulls the registry-delivered versioned images back;
10. verifies OCI revision/version labels;
11. runs the clean production-shaped post-publish smoke test.

For each container unit, the candidate identity is:

```text
ghcr.io/<owner>/woobe-api:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-workers:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-frontend:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-embed:sha-<RELEASE_COMMIT>
```

The published version tags are digest-preserving promotions:

```text
canonical release commit
        ↓
multi-arch candidate build
        ↓
candidate smoke + attestations
        ↓
sha-<commit> immutable image
        ↓
v<VERSION> immutable Git tag
        ↓
digest-preserving promotion
        ↓
<VERSION> image tag
        ↓
registry-delivered smoke
```

Deletion of a Git tag or GitHub Release does not make an already-published GHCR version reusable. If `woobe-<unit>:<VERSION>` exists with different bytes, publication fails and a new Semantic Version must be selected.

## 14. Automatic GitHub Release

After post-publish smoke succeeds, `release.yml` automatically creates the GitHub Release for `v<VERSION>` using GitHub generated release notes and the title:

```text
Woobe v<VERSION>
```

Generated notes preserve pull-request provenance, contributor attribution, first-time contributor information when available and the comparison against the previous published tag.

`.github/release.yml` remains the configuration surface for generated-note categorization.

`CHANGELOG.md` remains the curated product/operator history, but it is not edited by the deterministic release PR. Changelog and documentation changes must land through normal development PRs before the release workflow is started. Generated GitHub Release notes do not replace that curated history.

If the GitHub Release already exists during an idempotent recovery run, the workflow preserves it instead of creating a second release.

After the GitHub Release is confirmed, the workflow removes `release/<VERSION>` when that branch still exists.

## 15. Human release gate and recovery

The normal release path has one intentional human authorization:

1. choose the target Semantic Version and start **Release Woobe**.

That action authorizes publication only if every technical release gate succeeds. The generated PR, exact-head validation, master freshness check, merge, candidate build, immutable tagging, image promotion, post-publish smoke, GitHub Release creation and release-branch cleanup are automatic.

If pre-merge CI does not pass, the workflow stops, leaves the release PR open and reports the blocking checks. Nothing is published.

Manual recovery remains available:

- run `release-candidate.yml` with an explicit `ref` to rebuild/revalidate an immutable candidate;
- run `release.yml` manually from an existing immutable `v<VERSION>` tag to retry publication;
- never run `release.yml` from `master` or another branch;
- never move/reuse a published Git tag or overwrite a versioned GHCR image with different bytes.

Current Core release units are:

- `woobe-core==<VERSION>` — Python domain/runtime package used by backend process images;
- `woobe-api:<VERSION>` — independently deployable API container;
- `woobe-workers:<VERSION>` — independently deployable background-execution container;
- `woobe-frontend:<VERSION>` — independently deployable administrative Web container;
- `woobe-embed:<VERSION>` — independently deployable ChatSurface container.

The release workflow promotes the four container units. Core is not published as a standalone container because it is a library/migration boundary rather than a process host.

Do not rebuild a release version from the tag after the candidate has passed. A defect requires a new commit and a new version; never move a published tag or replace an immutable version with different bytes.

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
4. The changelog contains the released version and date.
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
