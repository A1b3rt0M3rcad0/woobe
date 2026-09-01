# Repository and system tests

`tests/` contains validation that crosses package boundaries or verifies repository-level contracts. It is not a production package and no product runtime should depend on it.

## Main test surfaces

- `unit/` — isolated backend behavior.
- `integration/` — integration against real infrastructure and module boundaries.
- `architecture/` — repository topology, package direction and distribution invariants.
- `quality_gate/` — self-tests for the architecture quality-gate engine and policies.
- `contract/` — explicit external/internal contract validation.
- `security/` — security and trust-boundary tests.
- `performance/` — performance-oriented validation.
- `migrations/` — migration-chain and database evolution checks.
- `modules/` and `messaging/` — module-level and messaging behavior.
- `fakes/` — deterministic fake providers and fixtures used by validation flows.
- `e2e/` — black-box validation of the assembled product, including Playwright/full-stack scenarios and release fixtures.

The canonical standalone backend validation topology is defined by root `compose.test.yaml`. E2E remains a test surface even when it builds and exercises deployable artifacts.
