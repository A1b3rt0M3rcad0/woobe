# Releasing Woobe SDK

This document is the canonical release procedure for the Woobe Python SDK.

A release is an immutable, reviewed repository state identified by a Python package version, a Git tag and the corresponding published distribution artifacts.

## Versioning policy

The canonical package version lives in `pyproject.toml`.

Stable releases use:

```text
MAJOR.MINOR.PATCH
```

Pre-releases use PEP 440 forms:

```text
0.1.0a1
0.1.0b1
0.1.0rc1
```

Git tags add a `v` prefix to the exact package version:

```text
v0.1.0a1
v0.1.0rc1
v0.1.0
```

Do not maintain a second independent version constant unless the public API later requires one.

Before 1.0.0 the SDK is pre-stable. Breaking public-API changes may occur, but they must be intentional, documented and represented by an appropriate release version. After 1.0.0, follow normal Semantic Versioning compatibility expectations.

## Branch model

`master` is the integration branch.

Normal work uses focused branches and pull requests. A release is prepared from reviewed `master` through:

```text
master
  |
  +-- release/<VERSION>
          |
          +-- version update
          +-- changelog
          +-- release notes/documentation
          +-- final validation
          |
          +-- PR -> master
                    |
                    +-- tag v<VERSION>
                    +-- PyPI publication
                    +-- GitHub Release
```

Do not place unrelated features on a release branch.

## 1. Select the version

Review all user-visible changes since the previous published SDK tag.

Classify:

- breaking public API or behavioral changes;
- backward-compatible features;
- bug/security fixes;
- dependency and minimum-Python changes;
- Runtime protocol compatibility changes.

Choose the package version before editing release files.

## 2. Create the release branch

Create `release/<VERSION>` from the exact `master` commit intended as the release baseline.

Example:

```bash
git checkout master
git pull --ff-only origin master
git checkout -b release/0.1.0a2
git push -u origin release/0.1.0a2
```

The canonical release-preparation commit/PR title is:

```text
chore(release): prepare Woobe SDK v<VERSION>
```

## 3. Update the package version

Update only the canonical version in `pyproject.toml`.

Search the repository for the previous version and inspect remaining matches manually. Do not mass-replace protocol versions, example values or unrelated data.

The Git tag must exactly equal `v` plus the package version.

## 4. Update the changelog

Move relevant entries from `## Unreleased` into a dated release section.

Example:

```markdown
## Unreleased

## [0.1.0a2] - 2026-09-24

### Added
- ...

### Changed
- ...

### Fixed
- ...
```

The changelog is for users of the SDK, not a raw commit log.

Call out:

- public API changes;
- changed Runtime protocol expectations;
- minimum Python/dependency changes;
- retry, reattach or duplicate-Run behavior changes;
- required migration steps.

## 5. Review documentation and compatibility

At minimum review:

- `README.md`;
- `docs/ARCHITECTURE.md`;
- `docs/RUNTIME_STREAMING.md`;
- `docs/UPGRADING.md`;
- `SECURITY.md`;
- public examples;
- `pyproject.toml`.

If a Runtime API change is required for the SDK release, state the compatibility requirement explicitly. Do not imply compatibility that was not validated.

## 6. Review package and legal boundaries

Confirm:

- `LICENSE.md` is the MIT license;
- `pyproject.toml` declares `license = "MIT"`;
- the built wheel and sdist contain the expected license metadata/files;
- new third-party material has known provenance;
- `THIRD_PARTY_NOTICES.md` is updated when required;
- Woobe brand usage remains consistent with `TRADEMARKS.md`;
- the SDK release does not imply that MIT applies to the Woobe server.

## 7. Validate

From a clean environment:

```bash
python -m pip install -e '.[dev]'
ruff check .
pytest
rm -rf dist build
python -m build
twine check dist/*
```

Inspect the resulting wheel and sdist. Confirm that no credentials, local files, caches or unintended modules are packaged.

The GitHub CI package job must also be green.

## 8. Prepare release notes and contributors

Release notes should contain:

- concise release summary;
- breaking changes and migration actions;
- notable additions/fixes;
- Runtime compatibility notes;
- dependency or Python support changes;
- contributors represented by merged pull requests in the release range.

For the first public release, where no previous release tag exists, record an explicit baseline commit from the publishable repository history and compute release-note/contributor accounting from that baseline. Do not invent a fake `v0.0.0` release.

Generated GitHub notes may complement the curated changelog but do not replace compatibility/migration notes.

## 9. Merge the release PR

The release PR targets `master` and should be squash-merged with:

```text
chore(release): prepare Woobe SDK v<VERSION>
```

Do not tag the release branch before its release-preparation changes are merged to `master`.

## 10. Tag the exact release commit

After the release PR is merged and `master` is green:

```bash
git checkout master
git pull --ff-only origin master
git tag -a v<VERSION> -m "Woobe SDK v<VERSION>"
git push origin v<VERSION>
```

Published tags are immutable. Never move or reuse a release tag.

## 11. Automated publication

Pushing a `v*` tag triggers `.github/workflows/release.yml`.

The workflow:

1. verifies that the tag exactly matches the `pyproject.toml` version;
2. runs Ruff and pytest on supported Python versions;
3. builds the sdist and wheel;
4. runs `twine check`;
5. publishes to PyPI using GitHub OIDC Trusted Publishing;
6. creates the GitHub Release and attaches the built artifacts.

Before the first release, configure a PyPI Trusted Publisher for this repository/workflow and the GitHub `pypi` environment. No long-lived PyPI API token should be stored when Trusted Publishing is available.

## 12. Post-release verification

Verify:

- the Git tag resolves to the intended `master` commit;
- the PyPI project exposes the expected version;
- `pip install woobe-sdk==<VERSION>` succeeds in a clean environment;
- the installed package imports `Woobe`;
- the GitHub Release exists and contains the expected artifacts/notes;
- the wheel metadata reports MIT and the expected Python requirement.

Then delete the temporary release branch.

## Hotfixes

A hotfix starts from current `master` after the relevant fix is merged or from a focused release branch if the repository later supports maintained release lines.

Do not patch a published wheel or move an existing tag. Publish a new version.

## Failed or incorrect releases

PyPI files are immutable. If an uploaded release is materially wrong, correct the repository, increment the package version and publish a new release. Yank an unusable PyPI release when appropriate; do not overwrite it.

If a tag was pushed but publication did not complete, diagnose the workflow before creating another tag. Never force-move the published tag to a different commit.
