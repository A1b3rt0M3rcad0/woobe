# MVP execution log

## Stage 00 — frontend baseline

Merged into `development-mvp` through PR #13. Baseline documentation was captured before product changes.

## Stage 01 — CI and quality gates

Merged through PRs #14, #15, and #18. Backend, frontend, migrations, container build, container smoke, and the known-failure baseline became mandatory gates.

## Stage 02 — authentication and tenancy

Merged through PR #19 after the four principal workflows passed.

## Stage 03 — API keys and runtime security

Merged through PR #20 after backend, frontend, migrations, and containers passed. The PR records key lifecycle, scopes, isolation, limits, redaction, and HTTP tool protections.

## Stage 04 — playground streaming

Merged through PR #21 after backend, frontend, migrations, and containers passed.

## Stage 05 — dashboard overview API

Branch: `feat/mvp-05-dashboard-overview-api`  
PR: #22  
Target: `development-mvp`

Implemented the tenant-scoped dashboard read model, indexes, contracts, integration fixtures, performance acceptance, UTC bucketing, and CoreUnitOfWork integration. The first backend run exposed one new architecture-baseline failure because the new composer bypassed `CoreUnitOfWork`; the implementation was corrected to execute all seven overview queries inside the request unit of work.

Final merge is authorized only after all four principal workflows pass on the final head and the PR is marked ready for review.

## Closeout audit — stages 00 through 04

Branch: `mvp-closeout-audit`  
Base SHA: `30ddd69be9386d6c0730f9647f3caf7a6f561c55`  
Target: `development-mvp`

The audit found incomplete historical evidence in stage 00, a backend gate masking 152 current pytest failures, missing refresh-session replacement lineage, and three confirmed playground UI gaps: no stop control, unsupported providers still offered, and stale selection after credential creation.

Corrections on the audit branch:

- exact shrink-only pytest debt allowlist, reduced from 178 to 152 hashes;
- migration/model/runtime linkage for rotated refresh sessions;
- progressive-stream and single-terminal-event tests;
- visible playground stop action;
- OpenAI/OpenAI-compatible provider restriction;
- refreshed credential collection used for post-create selection;
- audited stage-04 status and full closeout report in `docs/mvp/closeout-audit-00-04.md`.

The audit does not authorize promotion to `development`. Remaining P0 blockers include eliminating the pytest allowlist and adding the cross-tenant, API-key isolation and cancellation/stream-contract integration matrices.
