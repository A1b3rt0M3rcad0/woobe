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

The primary technical isolation unit is Project. Organization is the commercial/membership unit. Production runtime must use immutable Agent Releases or Network Releases rather than mutable Draft state.

Community/Core code lives under `src/modules/**` and `src/shared/**`; edition-specific backend code lives under `src/editions/**`. Cloud or future Enterprise code may depend on the shared core, but shared core packages must not import edition packages. Frontend code follows the same direction: edition-specific UI belongs under `web/src/editions/**`, with edition composition performed from `web/src/app/**` rather than from shared features.

## Scope discipline

Do not combine unrelated refactors with a feature or fix. Avoid helpers, reexports or abstractions that only move code without reducing a concrete problem.

## Public repository surface

The public repository is the product repository, not an archive of the internal development process.

Keep durable product code, tests, current documentation, supported deployment contracts and contribution tooling in the repository. Do not commit internal AI-agent prompts or skills, implementation journals, stage markers, generated evidence, one-off debugging stacks, completed refactor plans, internal execution logs or temporary audit artifacts.

Durable architecture decisions belong in `docs/adr/`. Current product behavior belongs in `docs/`. Work in progress belongs in Issues and pull requests rather than permanent `specs/` or `docs/mvp/` archives.

## Quality

The validation contract is the standalone root `compose.test.yaml`. It is intentionally separate from the Community distribution in `compose.yaml` and does not require Bash or WSL on the host.

Run the complete validation stack locally with the same command used by CI:

```bash
docker compose -f compose.test.yaml up --build --exit-code-from tests tests
```

The aggregate `tests` service only completes after backend, frontend, mocked-browser, and full-stack browser suites complete successfully. After a local run, clean the validation stack with `docker compose -f compose.test.yaml down -v --remove-orphans`.

For focused diagnosis, individual suites can be executed with `docker compose -f compose.test.yaml run --rm --build <service>`, where `<service>` is `backend-tests`, `frontend-tests`, `browser-mocked`, or `browser-e2e`.

The manual `tests.yml` workflow executes the exact same full-validation Compose command. Container, acceptance, security, and release workflows remain separate because they validate production images, the actual Community distribution, repository security, and publishing respectively. Repository workflows are intentionally executed only when validation is requested.

See [Compose test workflow](docs/testing/COMPOSE_TESTS.md) for the test topology and suite responsibilities.

## Licensing contributions

By submitting a contribution, you represent that you have the right to submit it under the repository's contribution terms. Woobe may introduce a formal Contributor License Agreement before accepting external contributions that require relicensing flexibility.
