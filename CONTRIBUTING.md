# Contributing to Woobe

Woobe uses `master` as the integration branch.

## Workflow

1. Create a focused branch from the latest `master`.
2. Keep the change small and scoped to one concern.
3. Preserve existing package, module and domain boundaries.
4. Add or update tests for behavior you change.
5. Update documentation when public behavior, contracts, licensing or operations change.
6. Open a pull request targeting `master`.
7. Merge only according to repository policy.

Recommended branch prefixes: `feature/`, `fix/`, `chore/`, `docs/` and `ci/`.

## Product boundaries

Woobe has two software boundaries:

- **Core** — source-available code under `packages/woobe-core`, `packages/woobe-api`, `packages/woobe-workers`, `packages/woobe-runtime-client`, `packages/woobe-ui`, `packages/woobe-frontend` and `packages/woobe-embed`.
- **Enterprise** — material covered by `LICENSE_EE.md`, originally under `packages/woobe-ee/**`, with non-production permissions and separately authorized Production Use.

External contributions should target Core unless a maintainer explicitly requests an Enterprise-boundary change. Do not copy Enterprise implementation into Core packages or make `woobe-core` depend on Enterprise code. Independent integration code is not relicensed merely because it imports or invokes EE; that licensing rule does not relax architectural dependency rules or grant Enterprise Production Use rights. Core deployments must remain runnable without activating Enterprise implementation.

See `LICENSE.md`, `LICENSE_EE.md` and `LICENSING.md` before changing edition boundaries.

## Repository architecture

Organization is the commercial account boundary. Project is the primary technical isolation boundary. Production runtime must use immutable Agent Releases or Network Releases rather than mutable Draft state.

The repository has three main code/validation concerns:

- `packages/` — product and distributable artifacts.
- `tooling/` — engineering-only packages: `woobe-testkit`, `woobe-mock` and `quality-gate`.
- `tests/` — repository and cross-system validation, including architecture, contracts, integration, security and E2E.

API and Workers may depend on Core. Core must not depend on API, Workers or Enterprise implementation. Frontend and Embed consume HTTP contracts rather than importing Python Core. Product runtime packages must not depend on `tooling/`. Tests and tooling may depend on product packages for validation.

Alembic configuration and migration history remain under `packages/woobe-core`.

Bounded-context `presentation` and `composition` code intentionally stays with its owning module in `woobe-core`; process-level FastAPI bootstrap and transport composition belong to `woobe-api`. See `docs/adr/0004-package-workspace-and-process-boundaries.md`.

## Scope discipline

Do not combine unrelated refactors with a feature or fix. Avoid helpers, reexports or abstractions that move code without solving a concrete problem.

Critical rules belong in the backend. Frontend checks must not be the only barrier for ownership, permissions, release immutability, rollback, document uniqueness, credential security or runtime authorization.

## Licensing, brand and third-party changes

Changes that touch licensing, Enterprise boundaries, notices, container distribution, package metadata, repository branding or Woobe trademarks require explicit review.

Do not add third-party code, assets, images or generated material without clear provenance and license compatibility. Update `THIRD_PARTY_NOTICES.md` when a distributed dependency creates attribution or notice obligations.

Brand assets are governed separately by `TRADEMARKS.md`; do not assume the software license grants rights to reuse Woobe branding.

## Quality

The standalone backend validation contract is root `compose.test.yaml`:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

Clean the validation stack with:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

Container, acceptance, security, quality-gate and release workflows are separate validation surfaces. The architecture gate lives under `tooling/quality-gate`.

See `docs/testing/COMPOSE_TESTS.md` for the current topology.

## External contributions

External contributors must read `CONTRIBUTOR_LICENSE_AGREEMENT.md` and explicitly accept it in the pull request body using the checkbox provided by the pull request template.

The CLA allows Woobe to use and relicense contributions across Core and separately licensed Enterprise products while contributors retain their underlying ownership rights.

Do not merge an external contribution while the CLA check is failing.

## Security

Do not publish secrets, access tokens, customer data or non-public vulnerability details in issues or pull requests. Security reports must follow `SECURITY.md`.
