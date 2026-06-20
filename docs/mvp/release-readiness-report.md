# MVP release-readiness report

## Decision

**Status while the pull request is open: NO-GO.**

This status is procedural, not a known product failure. Promotion is blocked until every mandatory workflow passes on the final commit and the pull request is reviewed. A green pull request may change the recommendation to **GO WITH RESTRICTIONS**; staging evidence and the final human approval remain required before the release-candidate tag.

## Scope

Branch: `test/mvp-08-e2e-release-hardening`  
Base: `development-mvp`  
Base commit: `5261bfef2615289fec8676e5ed7e139adb024929`  
Target: `development-mvp`

Feature development is frozen in this stage. The diff is restricted to tests, release gates, deterministic fixtures and release documentation.

## Mandatory evidence matrix

| Gate | Automated evidence | Initial state |
|---|---|---|
| onboarding and workspace | Chromium registration, tenant selection and project dashboard | pending CI |
| agent and playground | agent creation, SSE response, persisted session reload | pending CI |
| API-key lifecycle | one-time secret presentation plus existing revoke/rotate backend matrix | pending CI |
| cross-tenant negative matrix | PostgreSQL resource-family authorization tests and browser 404 | pending CI |
| provider behavior | success, streaming, fallback, tool call, failure, latency and cancellation | pending CI |
| migrations | empty upgrade, downgrade one revision, re-upgrade and drift check | pending CI |
| backup/restore | custom-format backup, checksum and isolated-database restore probe | pending CI |
| controlled load | sync and streaming p50/p95/p99, TTFT, throughput and error rate | pending CI |
| production images | immutable builds, production Compose smoke, graceful stop and restart | pending CI |
| OWASP baseline | headers, topology, secrets template, CORS and IDOR contracts | pending CI |
| flakiness | Playwright retries fixed at zero; failures are not masked | pending CI |

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
