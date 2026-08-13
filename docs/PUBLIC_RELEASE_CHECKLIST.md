# Woobe public release checklist

This checklist is a release gate for making the Woobe repository and Community distribution public. It is intentionally stricter than normal development completion.

## Repository surface

- [ ] Root `compose.yaml` is the only supported default Community self-host contract.
- [ ] Root `compose.test.yaml` is a standalone validation contract and is not presented as a product distribution.
- [ ] Development-only infrastructure is explicit under `deploy/dev/` and is not presented as a product distribution.
- [ ] No proprietary Cloud or Enterprise implementation is present in the public Community HEAD or Community build contexts.
- [ ] No obsolete `deploy/test/` overlay, host-shell test orchestrator, `.opencode/`, `opencode.json`, internal `specs/`, `docs/mvp/`, stage markers, execution journals, generated evidence, one-off debugging stacks, or obsolete one-off migration scripts remain in the public HEAD.
- [ ] Exactly one pull request template exists under `.github/`.
- [ ] Browser acceptance tests use the root `e2e/` package; Python tests use the taxonomy under `tests/` without a competing `tests/e2e/` namespace.
- [ ] Durable runtime and testing documentation is under `docs/` and describes current behavior rather than implementation history.
- [ ] Legacy codename strings have been reviewed across the public tree and either removed or justified as historical compatibility where technically required.

## Secrets, proprietary source and Git history — blocking

Deleting a file from the current branch does **not** remove it from Git history.

Before changing repository visibility:

- [ ] Run the full-history audit with `scripts/audit_public_history.sh`. The script scans secrets across all reachable refs and fails when known proprietary implementation paths remain reachable.
- [ ] Review findings manually; rotate or revoke every real credential that has ever been committed, even if the file was later deleted.
- [ ] Review any historical proprietary-path report and confirm Cloud/Enterprise/Billing implementation cannot become public merely because it was removed from the current HEAD.
- [ ] Decide and execute the public-history strategy: either rewrite/sanitize existing history or publish from a deliberately sanitized public baseline.
- [ ] Verify branches and tags that will become visible, not only the current `development` HEAD.
- [ ] Re-run the history audit against the exact repository state intended for publication.

Do not make the repository public while this section is incomplete.

## Community deployment

- [ ] Generate a fresh `.env` using `python scripts/generate_self_host_env.py`.
- [ ] Validate the root `compose.yaml` configuration.
- [ ] Start the complete Community stack from the root Compose contract.
- [ ] Confirm persistent PostgreSQL, RabbitMQ, and Knowledge volumes.
- [ ] Exercise a production-shaped configuration with secure cookies, exact HTTPS CORS origins, exact trusted hosts, and distinct strong secrets.
- [ ] Verify API `/live` and `/ready`, Web, Workers, and ChatSurface health/assets.
- [ ] Verify first-owner bootstrap and invite-only behavior after initialization.
- [ ] Verify backup and restore with PostgreSQL plus local Knowledge files.

## Quality and security

- [ ] Validate the standalone test contract with `docker compose -f compose.test.yaml config --quiet`.
- [ ] Run the full local/CI validation contract with `docker compose -f compose.test.yaml up --build --exit-code-from tests tests`; the manual tests workflow must execute this exact same command.
- [ ] Confirm backend mocked and backend integration suites complete successfully through their dedicated `docker/tests/Dockerfile.*` images.
- [ ] Confirm the test topology uses Docker service DNS rather than `host.docker.internal` and requires no host Bash/WSL dependency.
- [ ] Run the manual container workflow: builds, non-root checks, SPDX SBOM generation, third-party dependency inventory, and HIGH/CRITICAL image scanning.
- [ ] Run the manual acceptance workflow: backup/restore and production-shaped Community smoke against the actual root `compose.yaml` distribution.
- [ ] Run the manual security workflow and the full-history audit script.
- [ ] Review unresolved HIGH/CRITICAL findings and document accepted risk explicitly.

## Licensing and repository administration — blocking

- [ ] Qualified counsel has reviewed `LICENSE.md`, `LICENSING.md`, `CONTRIBUTOR_LICENSE_AGREEMENT.md`, trademark terms and the external contribution strategy for the intended jurisdictions.
- [ ] The repository CLA text and acceptance workflow are enabled, and the CLA check is required by branch protection before external contributions are merged.
- [ ] Run the container workflow for the exact release artifacts, review the generated `woobe-third-party-inventory`, and include every notice or attribution required by the original component licenses.
- [ ] Community build artifacts have been inspected to confirm proprietary edition source is absent.
- [ ] GitHub default branch is the intended public integration branch.
- [ ] Branch protection/rulesets are configured for the public workflow.
- [ ] Private vulnerability reporting/security contact is configured.
- [ ] Repository description, topics, homepage/docs URL, and package/container visibility are correct.

## Release

- [ ] Version is selected according to the release policy.
- [ ] Changelog/release notes describe user-visible changes and migration considerations.
- [ ] Published images correspond to the reviewed commit.
- [ ] Final public tree contains only product code, tests, current documentation, supported deployment contracts, and contribution/governance files.
