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
v0.1.0
v0.1.1
v0.2.0
v1.0.0
```

Container/image versions and release workflow inputs use the version without the `v` prefix.

Before `1.0.0`, Woobe is explicitly pre-stable. The project still uses the following practical policy:

- PATCH (`0.1.0 -> 0.1.1`) for compatible fixes, security fixes and release corrections.
- MINOR (`0.1.x -> 0.2.0`) for meaningful feature releases and intentionally breaking pre-1.0 changes.
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

## 2. Create the release branch

Create `release/<VERSION>` from the exact current `master` commit intended to become the release baseline.

Example:

```bash
VERSION=0.2.0

git checkout master
git pull --ff-only origin master
git checkout -b "release/$VERSION"
git push -u origin "release/$VERSION"
```

Record the baseline commit if the release requires a formal audit.

## 3. Synchronize the Woobe platform version

All product artifacts that represent the same Woobe platform release must agree on `<VERSION>`.

### Python product manifests

Update:

- `pyproject.toml`
- `packages/woobe-core/pyproject.toml`
- `packages/woobe-api/pyproject.toml`
- `packages/woobe-workers/pyproject.toml`

Also update internal exact product dependencies that pin the platform version, currently including:

- `woobe-core==<VERSION>` in `packages/woobe-api/pyproject.toml`
- `woobe-core==<VERSION>` in `packages/woobe-workers/pyproject.toml`

Regenerate `uv.lock` after Python manifest changes. Do not hand-edit generated dependency resolution beyond what is required to resolve a lock-generation problem.

### Browser/product manifests

Update the product version in:

- `packages/woobe-runtime-client/package.json`
- `packages/woobe-ui/package.json`
- `packages/woobe-frontend/package.json`
- `packages/woobe-embed/package.json`

When a package has a lockfile, regenerate it from the corresponding manifest. Currently this includes:

- `packages/woobe-frontend/package-lock.json`
- `packages/woobe-embed/package-lock.json`

The manifest and the root package entry inside each generated lockfile must report the same platform version.

### Runtime/version metadata

Review first-party runtime metadata that exposes the Woobe platform version and update it when it represents the application release rather than a protocol or domain-object version.

Current version-bearing surfaces include:

- FastAPI application metadata in `packages/woobe-api/src/main.py`
- Woobe MCP client metadata in `packages/woobe-core/src/modules/agent/application/mcp_discovery.py`
- Woobe MCP OAuth/safety client metadata in `packages/woobe-core/src/modules/agent/application/mcp_oauth_flow_safety.py`

Search for the previous platform version after the explicit edits and inspect every remaining match manually. Do not automatically change matches belonging to examples, tests, Skills, Agent/Network Releases, protocol fixtures, migrations or third-party packages.

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

Validate the exact images intended for publication:

- successful multi-architecture build where supported;
- non-root execution;
- OCI license metadata;
- SBOM generation;
- third-party inventory;
- HIGH/CRITICAL vulnerability scanning according to repository policy;
- startup/readiness;
- representative production-shaped smoke tests.

Do not publish a different commit from the one that passed final release validation.

## 11. Prepare the release pull request

Open a pull request:

```text
release/<VERSION> -> master
```

A release PR should contain only release preparation and required blockers.

The PR description should include:

- target version;
- previous release/tag;
- scope summary;
- compatibility or migration notes;
- version files changed;
- validation performed;
- known limitations that belong in release notes;
- confirmation that release/legal/third-party gates were reviewed.

All required repository checks and reviews must pass before merge.

## 12. Merge and identify the immutable release commit

Merge the release PR to `master`.

Immediately after merge:

```bash
git checkout master
git pull --ff-only origin master
git log -1 --oneline
```

Verify that the checked-out commit is the intended release commit and that no unrelated commit entered `master` between final review and tagging.

If `master` advanced in a way that changes the release contents, do not tag blindly. Re-evaluate the exact commit being released.

## 13. Create the Git tag

Create an annotated tag from the exact reviewed release commit:

```bash
VERSION=0.2.0

git tag -a "v$VERSION" -m "Woobe v$VERSION"
git push origin "v$VERSION"
```

The tag is immutable release history.

Do not move, force-update or reuse a published release tag. If a published release contains a defect, publish a new version.

Before publishing artifacts, verify:

```bash
git rev-parse "v$VERSION^{commit}"
git rev-parse HEAD
```

They must identify the intended release commit.

## 14. Publish the GitHub Release

Create a GitHub Release from `v<VERSION>`.

Use:

```text
Woobe v<VERSION>
```

as the release title.

Release notes should summarize the changelog rather than duplicate every commit. Include:

- major user-visible changes;
- fixes;
- security-relevant changes when disclosure is appropriate;
- migration steps;
- configuration changes;
- breaking changes;
- upgrade prerequisites;
- links to relevant documentation.

The GitHub Release must point to the immutable tag, never to a moving branch.

## 15. Publish Core container images

The current release workflow is:

```text
.github/workflows/release.yml
```

It accepts the Semantic Version without the `v` prefix and publishes versioned Core images.

Run the workflow against the exact release tag/ref, not against a later `master` commit.

With GitHub CLI, the intended shape is:

```bash
VERSION=0.2.0

gh workflow run release.yml \
  --ref "v$VERSION" \
  -f version="$VERSION" \
  -f public_api_url="<PUBLIC_API_URL>" \
  -f public_chat_embed_url="<PUBLIC_CHAT_EMBED_URL>"
```

Verify the resulting artifacts correspond to the release commit and expected version.

Current Core image names are:

- `woobe-api:<VERSION>`
- `woobe-web:<VERSION>`
- `woobe-chat-embed:<VERSION>`

Do not publish an image under a release version when its source commit differs from the Git tag carrying that version.

If a moving alias such as `latest` is introduced in the future, it must be treated as a convenience pointer only. Immutable version tags remain the source of release identity.

## 16. Post-release verification

After publication:

1. Pull/install from the published release artifacts rather than the local build cache.
2. Start a clean installation.
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

## First public release: v0.1.0

The first public release follows the same procedure as every future release, with additional one-time checks.

For `v0.1.0`:

- audit the exact Git history and refs that will become public;
- resolve any real credential exposure before publication;
- complete the repository legal-review gates;
- confirm the source-available Core and Enterprise boundaries are intentional;
- confirm trademark and third-party notices are complete for the artifacts actually distributed;
- normalize every Woobe product manifest to `0.1.0`;
- regenerate all affected lockfiles;
- review and remove or rewrite the README pre-release warning as appropriate for the actual public-release status;
- ensure `SECURITY.md` describes the release line and `master`, not obsolete integration-branch terminology;
- establish the first dated `CHANGELOG.md` release section;
- create `v0.1.0` only after the release PR is merged and the exact merge result is revalidated.

At the time this procedure was introduced, `packages/woobe-embed/package.json` and its lockfile still reported `1.0.0` while the other primary product manifests reported `0.1.0`. The `v0.1.0` release preparation must normalize that discrepancy rather than publishing mixed platform versions.

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
