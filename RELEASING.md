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

The preferred release path is the **Release Woobe** GitHub Action. Starting this workflow is the human authorization to release the requested version if, and only if, the entire release transaction succeeds.

1. Open **Actions -> Release Woobe**.
2. Enter the target Semantic Version without the `v` prefix.
3. The workflow validates strict Semantic Version syntax, rejects an already published GitHub Release, and requires normal releases to advance beyond the canonical `VERSION`. The optional `allow_initial_version_rebase` input exists only for an explicit first-ever published release whose chosen public version is lower than a pre-release development version.
4. If `VERSION` already equals the requested version on `master` and no GitHub Release exists, the workflow enters post-merge recovery mode instead of trying to recreate the release PR. It resolves the exact historical merge commit of the merged `release/<VERSION>` PR (or, as a fallback, the existing immutable `v<VERSION>` tag) so later `master` commits cannot silently change the release revision. Any existing `v<VERSION>` tag must point to that recovered revision.
5. Otherwise, if `release/<VERSION>` already has an open PR targeting `master`, the workflow resumes that PR without rewriting the branch or creating another PR. An unrelated/orphan branch remains blocking.
6. It runs `scripts/release/set_platform_version.py <VERSION>`, validates the synchronized state with `scripts/ci/check_package_versions.py`, creates `release/<VERSION>`, and opens the normal release PR.
7. The release gate waits for the complete required CI matrix on the exact PR HEAD. Approval-required workflow runs are waited on; failed, cancelled, skipped or timed-out required checks block the release.
8. If `master` advances while validation is running, the release branch is refreshed from current `master` and the new exact HEAD must pass CI again.
9. Only a stable release HEAD with every required gate green is merged automatically.
10. The resulting merge commit becomes the only release revision. **Release Woobe** invokes **Release candidate images** as a reusable workflow for that exact SHA.
11. Candidate build produces API, Workers, Frontend and Embed images for both `linux/amd64` and `linux/arm64`. Existing immutable SHA candidates may be reused only after identity revalidation.
12. Candidate lookup is fail-closed: only an explicit registry not-found response permits a new build; authentication, timeout and transient registry failures abort.
13. Multi-architecture verification and production-shaped candidate smoke must pass.
14. The candidate reusable workflow returns the exact SHA256 digest for each of the four validated images plus a validation identity directly to the parent workflow. No GitHub Actions artifact is required for orchestration.
15. Only after candidate validation succeeds does **Release Woobe** create or verify the immutable Git tag `v<VERSION>` on the exact merge commit.
16. **Release Woobe** invokes **Publish Woobe Core images** as a reusable workflow and passes those exact digests. Tag creation no longer independently triggers publication.
17. Publication revalidates candidate digests/platforms and promotes those exact digests to the release version without rebuilding. Registry state must be conclusively `exists` or `not found`; an unknown/error state aborts.
18. Promotion is idempotent. If a version tag already exists with the expected digest, it is preserved and the workflow continues; a different digest blocks the release.
19. The published images are pulled and smoke-tested again. Only after this post-publish smoke succeeds is the GitHub Release created, a permanent `release-manifest.json` attached, and the release branch removed.
20. **Release Woobe reports success only after all upstream CI, candidate validation, digest promotion, post-publish smoke and GitHub Release creation have succeeded.** Reusable-workflow failure/cancellation propagates to the parent.

The candidate workflow keeps an optional manual `workflow_dispatch` entrypoint for diagnostics/revalidation. Publication is callable only by the parent through `workflow_call`; it cannot be started directly or by a tag push. Neither workflow is triggered by a `master` push or by a `v*` tag push. This removes the former race and prevents bypassing the successful candidate gate.

Release-child concurrency is serialized without cancellation. A second invocation for the same release SHA/version must wait; it must never cancel an in-progress candidate smoke or partial publication. External registry reads use bounded retries with explicit image/ref diagnostics.

For automatic PR creation and merge, enable **Settings -> Actions -> General -> Workflow permissions -> Allow GitHub Actions to create and approve pull requests**. With the default `GITHUB_TOKEN`, GitHub can place pull-request workflow runs in an approval-required state; the orchestrator waits for approval rather than treating `action_required` as test success or failure.

For CI that starts without this additional approval, configure the repository secret `WOOBE_RELEASE_TOKEN` with a GitHub App installation token or personal access token with Contents, Pull requests and Actions write access. The workflow uses it consistently for Git checkout/push and GitHub CLI operations.

`master` should also be protected at the GitHub repository level so direct pushes cannot bypass the PR/check contract. The release workflow performs a repository-policy preflight and emits a warning when GitHub reports `master` as unprotected. Repository protection is an account/repository setting, not something the source-controlled workflow can enable for itself.

If orchestration fails before merge, run **Release Woobe** again with the same version to resume the open release PR. If it fails after merge, run **Release Woobe** again with the same version: because `master/VERSION` already matches, it resolves the exact historical release merge and resumes post-merge finalization. Existing SHA candidates and correctly promoted version tags are reused safely, while candidate smoke and final publication checks are revalidated. If the GitHub Release was actually created before the parent workflow lost its status, the retry verifies the immutable tag/revision and returns successful idempotent completion instead of attempting to publish again. Do not delete or move a valid release tag as a normal retry mechanism.

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

A failed candidate does not create the release tag. Re-running **Release Woobe** with the same version after a post-merge failure recovers the exact historical merge revision and revalidates the candidate.

## 13. Immutable tag and container publication

After candidate validation succeeds, **Release Woobe** creates or verifies the annotated `v<VERSION>` Git tag on the exact validated merge revision.

Tag creation is not a publication trigger. `.github/workflows/release.yml` has no `push: tags` release path; normal publication is invoked explicitly by the parent as a reusable workflow.

Publication receives:

- exact platform version;
- exact release revision;
- candidate validation identity;
- API digest;
- Workers digest;
- Frontend digest;
- Embed digest.

Before promotion, publication re-inspects each `sha-<commit>` candidate and requires its registry digest and both architectures to match the candidate outputs.

For an existing `<VERSION>` image tag, registry lookup has three states:

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
v<VERSION> immutable Git tag
        ↓
digest-preserving GHCR promotion
        ↓
<VERSION> image tags
```

Partial promotion is recoverable. A retry preserves any version tag already pointing to the expected digest and continues with missing units. A conflicting digest permanently blocks reuse of that version.

## 14. Post-publish verification and permanent manifest

After promotion, the workflow pulls all four registry-delivered `<VERSION>` images, verifies their embedded revision/version labels and runs the production-shaped smoke contract again.

Only after that smoke succeeds does the workflow create the GitHub Release.

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

## 15. Human release gate and recovery

The normal release path has one intentional human authorization:

1. choose the target Semantic Version and start **Release Woobe**.

That action authorizes publication only if every technical gate succeeds.

The parent workflow is composed as:

```text
Release Woobe
  ↓
prepare/release PR + required CI + exact merge
  ↓
reusable Release candidate images
  ↓
immutable Git tag
  ↓
reusable Publish Woobe Core images
  ↓
post-publish smoke
  ↓
GitHub Release + permanent release-manifest.json
  ↓
release branch cleanup
```

Failure or cancellation propagates through the reusable workflow chain; there is no separate polling process that can silently lose the child status.

Recovery rules:

- **Before merge:** run **Release Woobe** again with the same version to resume the open release PR.
- **After merge but before GitHub Release:** run **Release Woobe** again with the same version. It resolves the historical merge commit of `release/<VERSION>`, reuses only candidates whose identity is valid, and resumes finalization.
- **After GitHub Release exists:** a retry verifies the immutable tag, downloads the permanent release manifest, verifies all four versioned registry digests, architectures and OCI labels, and completes any pending release-branch cleanup before returning success.
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
