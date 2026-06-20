# MVP release-readiness report

## Decision

**Status while the pull request is open: NO-GO pending human review.**

All mandatory automated workflows passed on head `24929af98f521b16c7241efd53682485ed2f6b70`. The remaining blocker is the release owner's review of the pull request and generated artifacts. After approval, the recommendation is **GO WITH RESTRICTIONS** because production traffic shape, external-provider variance and long-running staging behavior remain outside deterministic CI.

## Scope

Branch: `test/mvp-08-e2e-release-hardening`  
Base: `development-mvp`  
Base commit: `5261bfef2615289fec8676e5ed7e139adb024929`  
Validated head: `24929af98f521b16c7241efd53682485ed2f6b70`  
Target: `development-mvp`

Feature development is frozen in this stage. The diff is restricted to tests, release gates, deterministic fixtures and release documentation.

## Mandatory evidence matrix

| Gate | Automated evidence | Result |
|---|---|---|
| onboarding and workspace | Chromium registration, tenant selection and project dashboard | passed |
| agent and playground | agent creation, SSE response, persisted session reload | passed |
| API-key lifecycle | one-time secret presentation plus existing revoke/rotate backend matrix | passed |
| cross-tenant negative matrix | PostgreSQL resource-family authorization tests and browser 404 | passed |
| provider behavior | success, streaming, fallback, tool call, failure, latency and cancellation | passed |
| migrations | empty upgrade, downgrade one revision, re-upgrade and drift check | passed |
| backup/restore | custom-format backup, checksum and isolated-database restore probe | passed |
| controlled load | sync and streaming p50/p95/p99, TTFT, throughput and error rate | passed |
| production images | immutable builds, production Compose smoke, graceful stop and restart | passed |
| OWASP baseline | headers, topology, secrets template, CORS and IDOR contracts | passed |
| flakiness | Playwright retries fixed at zero; failures are not masked | passed |

## Observed deterministic-load evidence

- synchronous: 120 requests, concurrency 12, error rate 0%, p95 31.16 ms, p99 139.96 ms, throughput 606.89 requests/s;
- streaming: 80 requests, concurrency 8, error rate 0%, latency p95 17.97 ms, TTFT p95 11.46 ms, throughput 516.11 requests/s;
- release acceptance matrix: 30 tests, zero failures, zero errors and zero skipped tests;
- backup checksum: verified after restore into an isolated PostgreSQL database.

## Thresholds

The deterministic provider gate uses the following CI thresholds:

- synchronous p95 latency: at most 500 ms;
- streaming p95 latency: at most 750 ms;
- streaming TTFT p95: at most 250 ms;
- provider error rate: 0%;
- browser retries: 0;
- cross-tenant access: 0 successful foreign-resource reads;
- backup restore probe: exact value match after restore;
- migrations: one current head with successful rollback/re-upgrade.

These thresholds qualify the deterministic CI environment. They are not production capacity claims.

## Residual risks requiring staging or operational approval

1. Production traffic shape and provider-network variance are not represented by the local fake provider.
2. Long-running SSE connections under host termination require staging observation beyond the bounded Compose smoke.
3. Queue depth and database-pool saturation require telemetry from the target deployment size.
4. Backup RPO depends on the external backup schedule; CI validates integrity and restorability, not scheduling.
5. A release owner must inspect the generated artifacts and approve the final go/no-go decision.

## Promotion rule

Promotion to `development` or creation of an RC tag is forbidden when any mandatory workflow is red, cancelled, skipped unexpectedly or based on a superseded commit. The final decision must reference the exact pull-request head SHA and artifact set.
