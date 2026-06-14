---
name: projectrai-test-validation
description: Create and run ProjectRAI architecture, unit, integration, messaging, concurrency, migration, cleanup, and final validation tests for the agent migration.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: validation
  scope: tests-cleanup-reporting
---

# ProjectRAI Test, Cleanup, and Validation

Use this skill for specs `015` through `019`, `110` through `129`, `140` through `154`, or any request to validate, harden, clean up, or report the ProjectRAI `agent` migration.

The test suite is not decorative. It is the safety mechanism that allows incremental migration without losing modular-monolith boundaries.

## Test groups

Create or update tests in the appropriate group:

- `tests/architecture`: import boundaries, shared-layer restrictions, worker placement, agent boundaries, database boundaries, final architecture validation.
- `tests/modules/agent`: agent domain, application, infra, UoW, Outbox/Inbox repositories, use cases, routes, shims.
- `tests/workers` and `tests/messaging`: generic worker contracts, RabbitMQ publisher confirms, inbox/outbox processing, retry/dead-letter behavior.
- Migration tests: Alembic upgrade/downgrade, schema ownership, no cross-module FK.
- Compatibility tests: legacy route/module shims when temporarily present.
- Cleanup tests: no imports of removed legacy modules, no root worker business logic, no active allowlists.

## Architecture test principles

Prefer deterministic static checks. Use AST parsing for Python imports where feasible. Use text scanning only as a fallback or complement.

Boundary tests should fail on:

- `modules.ai`, `modules.knowledge`, or `modules.runtime` imports after the relevant cleanup specs.
- Cross-module internal imports.
- `shared` containing domain-specific entities, value objects, use cases, handlers, DTOs, or module-specific event handling.
- Concrete workers in `src/workers`.
- Root/shared workers with business event names, routing keys, or repository dependencies.
- Cross-module Foreign Keys in models or migrations.
- Final allowlist entries for legacy modules.

## Required behavior tests

For `agent`, cover:

- Use case success paths.
- Domain invariant failures.
- DTO/schema mapping.
- Repository persistence.
- Unit of Work commit/rollback.
- Outbox persistence in same transaction as state change.
- Inbox duplicate delivery behavior.
- Event mapper versioning.
- Route shim compatibility when present.

For workers/messaging, cover:

- Outbox claim with no double-claim under concurrency.
- Publish success marks `published` only after confirm.
- Publish failure returns to retryable/dead according to policy.
- Inbox consumer persists before ack.
- Processor invokes internal handler exactly once per idempotency key.
- Dead-letter behavior is observable and auditable.

## Cleanup rules

When specs deprecate or remove legacy modules:

1. Confirm deprecation specs are complete before deletion specs.
2. Confirm shims exist and are tested before any breaking route/module change.
3. Remove imports before removing files.
4. Remove or update Alembic metadata imports.
5. Remove root worker business logic.
6. Remove temporary allowlist entries only after tests pass without them.
7. Do not delete data or database structures unless the active spec and migration phase explicitly allow it.

Final expected state includes:

- `src/modules/agent` exists.
- `src/modules/ai`, `src/modules/knowledge`, and `src/modules/runtime` do not exist.
- No `modules.ai`, `modules.knowledge`, or `modules.runtime` imports remain.
- `src/workers` is absent or contains no concrete business workers.
- Architecture tests pass.
- Agent tests pass.
- Worker/messaging tests pass when directories exist.
- Alembic upgrade/downgrade passes.
- No cross-module FKs remain.
- Runtime and final migration report are updated.

## Validation command matrix

Run the active spec's commands. Common baseline:

```bash
ruff check src tests
pytest
pytest tests/architecture
pytest tests/modules/agent
pytest tests/workers tests/messaging
alembic upgrade head
alembic downgrade -1
alembic upgrade head
```

Use existence checks before optional directories:

```bash
test -d tests/workers && pytest tests/workers || true
test -d tests/messaging && pytest tests/messaging || true
```

Final grep checks:

```bash
rg "modules\.(ai|knowledge|runtime)" src tests || true
find src/modules -maxdepth 1 -type d | sort
find src/workers -maxdepth 2 -type f 2>/dev/null || true
rg "ForeignKey\(.*(ai|knowledge|runtime)\." src tests migrations || true
rg "op\.create_foreign_key|FOREIGN KEY" migrations src/modules || true
```

Do not treat `|| true` output as success. It exists to keep scans from aborting; inspect whether matches are allowed by the active spec.

## Final report requirements

For spec `154`, produce an evidence-based final report. Include:

- Specs executed and status.
- Files changed by phase.
- Commands run and exit codes.
- Architecture boundary result.
- Database FK classification result.
- Event topology summary.
- Legacy modules/routes/shims status.
- Remaining risks or explicit statement that no known blockers remain.
- Rollback notes for database changes.

Do not conclude the migration is complete if any required final checklist item is unverified.
