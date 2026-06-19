# Retired transition-test inventory

This document records test files removed from the active suite during the MVP 00–04 completion pass.

## Retirement rule

A test was retired only when it asserted an intermediate migration state that is no longer part of the current architecture. Typical examples were hard-coded Alembic heads (`0014`, `0019`, `0020`), the former standalone `tools` bounded context after its consolidation into `agent`, non-empty migration allowlists, source-code substring assertions for superseded worker registries, or specification files that were deleted together with the completed architecture migration.

No current behavioral, authorization, tenancy, API-key, streaming, persistence, migration-head, or architecture-boundary test is retired by this change. Current contract tests remain active, and missing MVP acceptance coverage is added separately.

## Superseding gates

The retired transition checks are superseded by:

- the single-head Alembic workflow, empty-database upgrade and `alembic check`;
- canonical tests under `tests/modules/**` for current bounded contexts;
- current event, outbox, runtime, security and observability tests;
- active layer-boundary tests that inspect the present dependency graph;
- container build and smoke workflows;
- the MVP completion integration matrices for tenancy, API keys and streaming.

## Retired groups

- staged architecture migration tests named `test_spec_*`, `test_add_*`, `test_remove_legacy_*`, `test_normalize_*`, `test_make_*` and `test_audit_*`;
- tests requiring the removed `modules.tools` package;
- tests pinning obsolete event names or pre-consolidation worker class names by source substring;
- migration implementation-characterization tests already covered by full-chain migration execution;
- duplicate legacy observability and outbox tests superseded by canonical suites.

The Git history remains the source of record for the removed files. Reintroducing one requires updating it to the current architecture and demonstrating non-duplicate coverage.