# Contributing to Woobe

Woobe uses `master` as the integration branch.

## Workflow

1. Create a focused branch from the latest `master`.
2. Keep the change small and scoped to one concern.
3. Preserve existing package, module, and domain boundaries.
4. Add or update tests for behavior you change.
5. Open a pull request targeting `master`.
6. Merge only according to repository policy.

Recommended branch prefixes: `feature/`, `fix/`, `chore/`, `docs/` and `ci/`.

## Architecture

Business rules belong in the backend. Frontend checks must not be the only barrier for ownership, permissions, release immutability, rollback, document uniqueness, credential security, or runtime authorization.

The primary technical isolation unit is Project. Workspace is the commercial/membership unit. Production runtime must use immutable Agent Releases or Network Releases rather than mutable Draft state.

The repository has three top-level code/validation concerns:

- `packages/` — product and distributable artifacts.
  - `packages/woobe-core` — bounded contexts, domain/application code, shared technical infrastructure, runtime contracts, bounded-context presentation/composition code, and Alembic migrations.
  - `packages/woobe-api` — HTTP process composition root.
  - `packages/woobe-workers` — worker process composition root.
  - `packages/woobe-frontend` — administrative control-plane frontend.
  - `packages/woobe-embed` — independently built/deployed ChatSurface embed.
  - `packages/woobe-ee` — reserved boundary only; Community must not depend on proprietary implementation.
- `tooling/` — engineering-only packages: `woobe-testkit`, `woobe-mock`, and `quality-gate`.
- `tests/` — repository and cross-system validation, including architecture, contracts, integration, security, and E2E.

API and Workers may depend on Core. Core must not depend on API, Workers, or Enterprise implementation. Frontend and Embed consume HTTP contracts rather than importing Python Core. Product runtime packages must not depend on `tooling/`. Tests and tooling may depend on product packages for validation.

Alembic configuration and migration history remain under `packages/woobe-core`; extracting them into a separate database package is a separate change.

Bounded-context `presentation` and `composition` code intentionally stays with its owning module in `woobe-core`; process-level FastAPI bootstrap and transport composition belong to `woobe-api`. See `docs/adr/0004-package-workspace-and-process-boundaries.md`.

## Scope discipline

Do not combine unrelated refactors with a feature or fix. Avoid helpers, reexports, or abstractions that only move code without reducing a concrete problem.

## Public repository surface

Keep durable product code, tests, current documentation, supported deployment contracts, and contribution tooling in the repository. Durable architecture decisions belong in `docs/adr/`; current product behavior belongs in `docs/`; work in progress belongs in Issues and pull requests.

## Quality

The standalone backend validation contract is root `compose.test.yaml`:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

Clean the validation stack with:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

The backend validation topology uses dedicated mocked and integration test images. Container, acceptance, security, quality-gate, and release workflows are separate validation surfaces.

The architecture gate lives under `tooling/quality-gate`; its self-tests remain part of the repository test surface under `tests/quality_gate`.

See `docs/testing/COMPOSE_TESTS.md` for the current topology.

## External contributions

External contributors must read `CONTRIBUTOR_LICENSE_AGREEMENT.md` and explicitly accept it in the pull request body using the checkbox provided by the pull request template. The `CLA acceptance` workflow verifies that acceptance for contributors who are not repository owners, members, or collaborators.

Do not merge an external contribution while the CLA check is failing. Public release still requires the legal and repository-governance review listed in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
