# Contributing to Woobe

Woobe uses `development` as the integration branch.

## Workflow

1. Create a focused branch from the latest `development`.
2. Keep the change small and scoped to one concern.
3. Preserve existing module boundaries and domain rules.
4. Add or update tests for behavior you change.
5. Open a pull request targeting `development`.
6. Do not merge your own PR unless repository policy explicitly permits it.

Recommended branch prefixes: `feature/`, `fix/`, `chore/`, `docs/` and `ci/`.

## Architecture

Business rules belong in the backend. Frontend checks must not be the only barrier for ownership, permissions, release immutability, rollback, document uniqueness, credential security or runtime authorization.

The primary technical isolation unit is Project. Workspace is the commercial/membership unit. Production runtime must use immutable Agent Releases or Network Releases rather than mutable Draft state.

The public Community product code lives under `src/modules/**`, `src/shared/**` and the shared frontend tree. Proprietary product implementation is not part of the Community source tree. Community code and build contracts must remain runnable without proprietary source.

## Scope discipline

Do not combine unrelated refactors with a feature or fix. Avoid helpers, reexports or abstractions that only move code without reducing a concrete problem.

## Public repository surface

The public repository is the product repository, not an archive of the internal development process.

Keep durable product code, tests, current documentation, supported deployment contracts and contribution tooling in the repository. Do not commit internal AI-agent prompts or skills, implementation journals, stage markers, generated evidence, one-off debugging stacks, completed refactor plans, internal execution logs or temporary audit artifacts.

Durable architecture decisions belong in `docs/adr/`. Current product behavior belongs in `docs/`. Work in progress belongs in Issues and pull requests rather than permanent `specs/` or `docs/mvp/` archives.

## Quality

The validation contract is the standalone root `compose.test.yaml`. It is intentionally separate from the Community distribution in `compose.yaml` and does not require Bash or WSL on the host.

Run the validation stack locally with the same command used by the manual tests workflow:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

After a local run, clean it with:

```bash
docker compose -f compose.test.yaml down -v --remove-orphans
```

The current validation topology is backend-focused and uses dedicated mocked and integration test images. Container, acceptance, security and release workflows remain separate and are intentionally executed only when validation is requested.

See `docs/testing/COMPOSE_TESTS.md` for the current topology.

## External contributions

External contributors must read `CONTRIBUTOR_LICENSE_AGREEMENT.md` and explicitly accept it in the pull request body using the checkbox provided by the pull request template. The `CLA acceptance` workflow verifies that acceptance for contributors who are not repository owners, members or collaborators.

Do not merge an external contribution while the CLA check is failing. Public release still requires the legal and repository-governance review listed in `docs/PUBLIC_RELEASE_CHECKLIST.md`.
