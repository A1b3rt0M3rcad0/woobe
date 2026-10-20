# Artifacts execution ledger

Source: [the supplied implementation plan](PLAN.md), preserved verbatim; its
SHA-256 and 60 ordered steps are recorded in [manifest.json](manifest.json).
Architecture decision: [ADR 0006](../../adr/0006-artifact-workspaces-document-runtime.md).
Baseline and ownership: [BASELINE.md](BASELINE.md).

Branch: `feat/artifact-workspaces-document-runtime`.
Base: `3dbcb3e1a7559f4a50ebca320e411933d46e8012`.

## Current state

Step 01 is complete. Baseline, ADR, ledger and CI guards are committed. The single
[PR #220](https://github.com/A1b3rt0M3rcad0/woobe/pull/220) is OPEN, Draft and has no
auto-merge. GitHub API connectivity recovered after the environment network draft
update; existing platform authentication worked without adding credentials.
PR #219 remains unrelated and untouched.

Step 02 is complete: exact pinned client snapshots, source/hash/license manifest,
local Go workspace and read-only client CI are included. Original client repositories
remain unchanged. CLI make check/build, both Go SDK modes, Python SDK 34 tests,
Ruff/build/Twine, source hashes and the new workflow validation passed. Step 03 is complete: domain identities/lifecycles, versioned DTOs, capability ports,
canonical schemas/fixtures and the Artifacts architecture policy are validated.
31 combined domain/contract/guard tests, Ruff and all nine architecture policies pass.
Persistence, authorization and adapters are not advertised as implemented. Step 04 is complete: additive PostgreSQL migration 0107, scoped catalog/revision
repositories and transactional Unit of Work passed 14 real PostgreSQL tests across
fresh and populated-upgrade paths. The native mocked regression passed 3135 tests
and 10 subtests. See PERSISTENCE.md.

Step 05 is complete: shared current-principal authority, explicit Artifacts Runtime
interface/actions, scoped live grants and restrictive Release/node intersection are
validated. 399 authority/Core/Artifacts regressions and 14 real PostgreSQL cases
passed. See AUTHORIZATION.md. Step 06 independent Workspace operations are next.

The stage commit carries `Plan-Step: 01/60`; a file never records its own containing
commit SHA. CI reconciles commit subjects/trailers against the execution manifest.
No final acceptance is claimed. Runtime capabilities are exposed only when their
authorization, service and adapter steps are implemented and validated.

## Validation and resumption

Local step 01 validation passed: 14 guard tests, Ruff for both new Python files,
117 combined quality-gate/architecture tests, and all eight governed module
architecture checks with zero violations. Commands and observed results are
recorded in the manifest; the initial API connectivity failure was resolved and PR creation/status verified.

Use the baseline commands and outcomes in BASELINE.md. Run the new guard tests
with `.venv/bin/python -m pytest -q tests/architecture/test_artifacts_plan_guard.py`.
Validate the ordered committed series with
`python3 scripts/validate_artifacts_plan.py --base 3dbcb3e1a7559f4a50ebca320e411933d46e8012`.
CI supplies its real PR event file and refuses non-Draft execution. Final audit
additionally supplies `--final` and requires exactly 60 completed, evidenced steps.

Never create empty commits or mark steps complete with placeholders. Correct a
step before committing it; later corrections require a controlled reconciliation
of its responsible commit. No merges, automatic mirrors, tags, production changes,
release/publication or Ready-for-review transition are part of this delivery.
