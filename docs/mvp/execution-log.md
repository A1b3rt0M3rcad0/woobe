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

The stage was merged only after the four principal workflows passed on the final head.

## Stage 06 — dashboard live UI

Merged into `development-mvp` through PR #27. The merge commit and stage-07 base are `df948536418e610b0baceb4eac5ad674270a93e0`.

## Stage 07 — production deployment

Original branch: `chore/mvp-07-production-deployment`  
Original base SHA: `df948536418e610b0baceb4eac5ad674270a93e0`  
Original PR: #28  
Original head SHA: `f573e5756ac6d93d75032bd26f9f15cbc1c262ed`  
Merge commit: `6df1bfd9f94ae7565fc92c2c77304af5154916f2`  
Target: `development-mvp`

PR #28 implemented production image hardening, a production Compose topology with a single migration job, fail-fast production configuration, liveness/readiness, worker process health, request/correlation IDs, structured and redacted logs, runtime metrics, backup/restore scripts, operational runbooks, container policy checks, SBOM generation and non-blocking vulnerability reports.

The Backend, Frontend, Migrations, Containers, and Production containers workflows completed successfully on the original head. The PR was nevertheless merged without a requested reviewer or recorded review discussion. Therefore, review approval was not a verified gate for the original merge.

Follow-up branch: `chore/mvp-07-production-deployment-review`  
Follow-up base SHA: `6df1bfd9f94ae7565fc92c2c77304af5154916f2`  
Follow-up target: `development-mvp`

The follow-up strengthens production-image evidence by requiring a cached rebuild with build-network access disabled, executing both images as non-root users, rejecting Vite/npm development commands in the frontend runtime image, and publishing deterministic image metadata including size and configured runtime identity. This follow-up must remain unmerged until code review and all applicable checks complete.

The following acceptance evidence remains environment-dependent and must not be marked complete solely from repository state: production smoke through the reverse proxy, graceful shutdown under active SSE/worker load, and a PostgreSQL backup/restore exercise in staging with measured RPO/RTO.

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
