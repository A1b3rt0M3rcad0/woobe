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

The preferred release-preparation path is GitHub Actions:

1. Open **Actions -> Prepare Woobe release**.
2. Run the workflow with the target Semantic Version without the `v` prefix.
3. The workflow validates the version and ensures that neither `v<VERSION>` nor `release/<VERSION>` already exists.
4. It runs `scripts/release/set_platform_version.py <VERSION>`.
5. It validates the synchronized state with `scripts/ci/check_package_versions.py`.
6. It creates `release/<VERSION>`, commits the synchronized release state, opens a Draft pull request and explicitly dispatches the release-branch CI workflows.

The workflow explicitly dispatches CI because pushes and pull requests created with the repository `GITHUB_TOKEN` do not recursively trigger ordinary workflow events.

The generated release PR remains Draft until changelog, documentation, compatibility notes and any release blockers have been reviewed.

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

A release PR should contain only release preparation and required blockers. Review and complete:

- target version;
- previous published release/tag;
- scope summary;
- compatibility or migration notes;
- changelog and public documentation;
- validation performed;
- known limitations that belong in release notes;
- release/legal/third-party review.

All required repository checks and reviews must pass before merge. The automated workflow dispatches the normal validation matrix for its generated branch; subsequent human edits to the PR trigger the ordinary pull-request workflows.

## 12. Merge and identify the immutable release commit

Merge the reviewed release PR using any repository-supported merge strategy. Release correctness does not depend on the merge commit subject.

The canonical platform release commit is the exact `master` commit that introduces the transition of root `VERSION` from the previous platform version to `<VERSION>`.

On a push to `master` that changes `VERSION`, `.github/workflows/release-candidate.yml`:

1. compares `VERSION` with the first parent;
2. validates every release-bearing mirror against canonical `VERSION`;
3. records the exact Git revision;
4. builds the four multi-architecture application images once;
5. publishes immutable `sha-<commit>` candidate tags with provenance/SBOM attestations;
6. verifies amd64 and arm64 manifests;
7. smoke-tests those exact candidate images.

The initial repository introduction of `VERSION` is treated as bootstrap and does not create a release candidate.

Wait for the candidate workflow for the exact release commit to succeed before creating the release tag. A failed or missing candidate must be corrected by a new reviewed release commit/version; do not tag a commit whose immutable candidate did not pass.

For controlled recovery or revalidation, `release-candidate.yml` also accepts a manual `ref` input. Manual candidate generation does not authorize moving or reusing an existing published tag.

Record the successful release commit SHA. If `master` advances afterward, tag that recorded commit explicitly rather than assuming the latest `master` commit is still the release commit.

## 13. Create the Git tag

Create an annotated tag from the exact reviewed release commit whose immutable candidate passed:

```bash
VERSION=0.15.0
RELEASE_COMMIT=<successful-release-candidate-commit-sha>

git tag -a "v$VERSION" "$RELEASE_COMMIT" -m "Woobe v$VERSION"
git push origin "v$VERSION"
```

The tag is immutable release history.

Do not move, force-update or reuse a published release tag. If a published release contains a defect, publish a new version.

Before publishing artifacts, verify:

```bash
git rev-parse "v$VERSION^{commit}"
printf '%s\n' "$RELEASE_COMMIT"
```

They must identify the same intended release commit.

The corresponding `sha-<commit>` release candidates must already exist and have passed the candidate workflow before this tag is created.

## 14. Publish the GitHub Release

Create a GitHub Release from `v<VERSION>`.

Use:

```text
Woobe v<VERSION>
```

as the release title.

Every Woobe GitHub Release has two complementary layers:

1. **Curated release notes** — maintained manually for users and operators.
2. **Change provenance** — derived from the pull requests actually included in the release.

The curated section should summarize the changelog rather than duplicate every commit. Include the sections that apply:

```markdown
# Woobe v<VERSION>

## Highlights

A short explanation of the most important changes in this release.

## New Features

### Feature name
User-facing explanation and relevant migration/usage notes.

## Improvements

### Improvement name
User-facing explanation.

## Bug Fixes

### Area or fix
User-facing explanation.

## Breaking Changes

Only when applicable.

## Upgrade Notes

Only when operator action, migrations or configuration changes are required.

---

## What's Changed

<generated PR list>

## New Contributors

<generated first-time contributor list, when applicable>

**Full Changelog**: <previous release or baseline>...v<VERSION>
```

Do not force empty editorial sections into the published notes. Omit sections that do not apply to the release.

### Pull request provenance and contributor credit

The `What's Changed` section is part of the release record and must preserve the relationship between the change, its pull request and its author.

The preferred entry shape is the one produced by GitHub generated release notes:

```markdown
* feat(runtime): add programmable execution by @contributor in #123
* fix(network): preserve session-scoped context by @contributor in #127
```

For each pull request included in the release:

- preserve the GitHub author attribution;
- preserve a link/reference to the pull request;
- use the merged PR title or an equivalent factual description;
- include the PR only when its merged change is actually reachable from the release tag;
- do not assign contribution percentages, line-count rankings or subjective contributor scores;
- do not replace an external contributor's attribution with the maintainer who merged the PR.

A contributor's participation is represented by the concrete PRs included in the release, not by an estimated percentage of the release.

Direct commits without a pull request may be represented separately when they materially affect the release, but normal development should continue to prefer pull requests so release provenance remains attributable.

### New contributors

When GitHub identifies a contributor whose first merged contribution is included in the release, preserve the generated `New Contributors` section.

Example:

```markdown
## New Contributors

* @alice made their first contribution in #123
* @bob made their first contribution in #127
```

This section is for human contributors. Automation accounts such as dependency/update bots and GitHub Actions are not treated as first-time community contributors.

### Generated release notes

Use GitHub generated release notes as the starting point for the provenance portion of the release. Repository configuration for generated notes lives at:

```text
.github/release.yml
```

The generated content is not a substitute for the curated `Highlights`, feature/fix explanations, breaking changes or upgrade notes. Maintainers should generate the PR/contributor section, then edit the release body without deleting valid author attribution.

The generated PR list must be checked against the exact release range. A pull request merged after the release tag, excluded from the release commit, or otherwise not reachable from the release tag must not be credited as part of that version.

### Full changelog link

For every release after the first public release, include a comparison from the immediately previous published platform tag:

```text
v<PREVIOUS_VERSION>...v<VERSION>
```

Example:

```text
v0.11.0...v0.12.0
```

The comparison link is the exhaustive repository-level reference. `CHANGELOG.md` remains curated product history and should not become a raw PR dump.

For the first public release, define and record an explicit initial release baseline commit for release-note and contributor accounting rather than inventing a `v0.0.0` tag. The baseline must belong to the publishable history.

The GitHub Release must point to the immutable tag, never to a moving branch.

## 15. Publish Core container images

The release workflow is:

```text
.github/workflows/release.yml
```

It does **not rebuild** the release images. The exact multi-architecture artifacts were already built, attested and smoke-tested by `.github/workflows/release-candidate.yml` from the canonical release commit.

For each container unit, the candidate identity is:

```text
ghcr.io/<owner>/woobe-api:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-workers:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-frontend:sha-<RELEASE_COMMIT>
ghcr.io/<owner>/woobe-embed:sha-<RELEASE_COMMIT>
```

After the immutable `v<VERSION>` tag exists, run `release.yml` against that tag:

```bash
VERSION=0.15.0

gh workflow run release.yml \
  --ref "v$VERSION" \
  -f version="$VERSION"
```

The workflow verifies that the tag, manifest version and canonical release commit agree. It then resolves the digest of each `sha-<RELEASE_COMMIT>` candidate and creates the version tag from that exact OCI manifest. The release step fails if the versioned tag does not resolve to the same digest.

This is a build-once/promote-exact-artifact contract:

```text
canonical release commit
        ↓
multi-arch candidate build
        ↓
candidate smoke + attestations
        ↓
sha-<commit> immutable image
        ↓
v<VERSION> tag
        ↓
digest-preserving promotion
        ↓
<VERSION> image tag
```

The workflow then pulls the published version tags back from GHCR, verifies their OCI revision/version labels and performs a clean production-shaped smoke test using the registry-delivered images. Publication is not considered successful until that post-publish smoke job passes.

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

1. One Semantic Version identifies the platform release.
2. All release-bearing product manifests agree on that version.
3. Generated lockfiles agree with their source manifests.
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
