# Woobe public release checklist

This checklist is the release gate for publishing Woobe Core source and Core distribution artifacts. It is intentionally stricter than normal development completion.

## Repository surface

- [ ] Root `compose.yaml` is the only supported default Woobe Core self-host contract.
- [ ] Root `compose.test.yaml` is validation infrastructure and is not presented as a product distribution.
- [ ] Development-only infrastructure is explicit under `deploy/dev/`.
- [ ] Core product packages are exactly `woobe-core`, `woobe-api`, `woobe-workers`, `woobe-frontend` and `woobe-embed`.
- [ ] `packages/woobe-ee` contains no Enterprise implementation in the Core release artifact/build context unless an explicit Enterprise release is being prepared under its own terms.
- [ ] `tests/e2e/` owns assembled browser/full-stack validation.
- [ ] Root legacy source surfaces (`src/`, `web/`, `embed`, `migrations`, `quality_gate`) are absent.
- [ ] Durable runtime/testing documentation reflects the current package topology and Core/Enterprise model.

## Secrets and Git history — blocking

Deleting a file from the current branch does not remove it from Git history.

- [ ] Run `scripts/audit_public_history.sh` against every ref intended for publication.
- [ ] Review all findings manually and rotate/revoke every real credential that has ever been committed.
- [ ] Confirm historical proprietary or separately licensed implementation cannot become public merely because it was removed from current HEAD.
- [ ] Decide and execute the publication-history strategy: sanitize existing history or publish from a deliberately sanitized baseline.
- [ ] Re-run the history audit against the exact commit and refs intended for publication.

Do not make the repository public while this section is incomplete.

## Core deployment

- [ ] Generate a fresh `.env` using `python scripts/generate_self_host_env.py` and confirm `WOOBE_EDITION=core` and `WOOBE_RUN_PERSISTENCE_MODE=event_journal`.
- [ ] Validate `docker compose config --quiet`.
- [ ] Start the complete Core stack from root `compose.yaml`.
- [ ] Verify PostgreSQL, MongoDB, RabbitMQ, Redis, migration, API, Workers, Web and ChatSurface behavior.
- [ ] Verify the Run journal worker drains Redis into MongoDB and that durability/barrier failures are surfaced rather than silently falling back to legacy persistence.
- [ ] Exercise production-shaped configuration with secure cookies, exact HTTPS origins, exact trusted hosts and independent strong secrets.
- [ ] Verify first-owner bootstrap, registration/invite policy and existing-installation bootstrap behavior.
- [ ] Verify backup/restore for PostgreSQL, MongoDB Run journal/checkpoints and Knowledge state.

## Quality and security

- [ ] Validate the standalone test contract with `docker compose -f compose.test.yaml config --quiet`.
- [ ] Run the backend validation contract `docker compose -f compose.test.yaml up --build --exit-code-from tests tests`.
- [ ] Run frontend tests/build and ChatSurface tests/typecheck/build.
- [ ] Run architecture/Quality Gate validation against the current package boundaries.
- [ ] Run container validation: builds, non-root checks, OCI Core license metadata, SPDX SBOM generation, third-party inventory and HIGH/CRITICAL image scanning.
- [ ] Run production-shaped acceptance including migrations, backup/restore, graceful restart and representative runtime smoke.
- [ ] Review unresolved security findings and document accepted risk explicitly.

## Licensing, contributions and brand — blocking

- [ ] Qualified counsel has reviewed `LICENSE.md`, `LICENSE_EE.md`, `LICENSING.md`, `CONTRIBUTOR_LICENSE_AGREEMENT.md` and `TRADEMARKS.md` for the intended jurisdictions/business model.
- [ ] The Core license clearly permits intended self-host/internal/product-infrastructure use and clearly defines the restriction on commercial resale/white-label/OEM/hosted sale of the Woobe system itself.
- [ ] `packages/woobe-ee` is explicitly excluded from the Core license grant and Enterprise terms are delivered separately when Enterprise code is distributed.
- [ ] The CLA acceptance mechanism is enabled and required for external contributions before merge.
- [ ] `PULL_REQUEST_TEMPLATE.md` requires product/license impact and third-party provenance review.
- [ ] Woobe name/logo/brand restrictions are separated from software rights and accurately documented in `TRADEMARKS.md`.
- [ ] Container images publish `org.opencontainers.image.licenses=LicenseRef-Woobe-Core-Sustainable-Use-1.0`.

## Third-party software — blocking

- [ ] Generate SPDX SBOMs for the exact API, Web and ChatSurface release images.
- [ ] Review the generated `woobe-third-party-inventory` against the original licenses.
- [ ] Include every required copyright notice, attribution, license copy, source offer or other distribution obligation.
- [ ] Confirm `THIRD_PARTY_NOTICES.md` and `NOTICE.md` match the exact release inventory.
- [ ] Re-run inventory review whenever a released dependency or base image changes.

## Repository administration

- [ ] GitHub default/integration branch is `master`.
- [ ] Branch protection/rulesets require the intended validation and CLA checks.
- [ ] Private vulnerability reporting/security contact is configured.
- [ ] Repository description, topics, homepage/docs URL and package/container visibility are correct.

## Release

- [ ] Version is selected according to release policy.
- [ ] Changelog/release notes describe user-visible changes and migration considerations.
- [ ] Published Core images correspond exactly to the reviewed commit and carry the expected license metadata.
- [ ] Final public tree contains only intended product code, Enterprise boundary marker/contracts, tests, current documentation, supported deployment contracts and contribution/governance files.
