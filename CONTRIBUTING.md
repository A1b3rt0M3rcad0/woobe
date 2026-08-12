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

## Scope discipline

Do not combine unrelated refactors with a feature or fix. Avoid helpers, reexports or abstractions that only move code without reducing a concrete problem.

## Public repository surface

The public repository is the product repository, not an archive of the internal development process.

Keep durable product code, tests, current documentation, supported deployment contracts and contribution tooling in the repository. Do not commit internal AI-agent prompts or skills, implementation journals, stage markers, generated evidence, one-off debugging stacks, completed refactor plans, internal execution logs or temporary audit artifacts.

Durable architecture decisions belong in `docs/adr/`. Current product behavior belongs in `docs/`. Work in progress belongs in Issues and pull requests rather than permanent `specs/` or `docs/mvp/` archives.

## Quality

The repository contains manual backend, frontend, container, acceptance, security and release workflows. Run only the checks relevant to your change locally; repository workflows are intentionally executed when validation is requested.

## Licensing contributions

By submitting a contribution, you represent that you have the right to submit it under the repository's contribution terms. Woobe may introduce a formal Contributor License Agreement before accepting external contributions that require relicensing flexibility.
