# MVP release-readiness report

## Decision

**NO-GO while the pull request is open, pending human review.**

The current pull-request checks are the source of truth for the effective head. When all checks are green and the release owner approves the evidence, the recommendation becomes **GO WITH RESTRICTIONS**. Production traffic shape, external-provider variance and long-running staging behavior remain outside deterministic CI.

## Scope

- branch: `test/mvp-08-e2e-release-hardening`;
- base: `development-mvp` at `5261bfef2615289fec8676e5ed7e139adb024929`;
- target: `development-mvp`;
- feature development is frozen; this diff is limited to tests, release gates, deterministic fixtures and documentation.

## Automated evidence

| Gate | Result |
|---|---|
| onboarding, workspace and live dashboard | passed |
| agent creation, SSE response and session reload | passed |
| API-key lifecycle and tenant denial | passed |
| provider success, streaming, fallback, tool call, failure, latency and cancellation | passed |
| migration upgrade, downgrade, re-upgrade and drift check | passed |
| PostgreSQL backup, checksum and isolated restore | passed |
| deterministic sync and streaming load | passed |
| production images, Compose smoke, graceful stop and restart | passed |
| OWASP configuration and private-resource authorization contracts | passed |
| Chromium E2E with zero retries | passed |

## Observed deterministic-load evidence

- synchronous: 120 requests, concurrency 12, error rate 0%, p95 31.16 ms, p99 139.96 ms, throughput 606.89 requests/s;
- streaming: 80 requests, concurrency 8, error rate 0%, latency p95 17.97 ms, TTFT p95 11.46 ms, throughput 516.11 requests/s;
- acceptance matrix: 30 tests, zero failures, zero errors and zero skipped tests;
- backup checksum verified after restore into an isolated database.

These numbers qualify the deterministic CI environment; they are not production capacity claims.

## Residual risks

1. Production provider and network variance require staging evidence.
2. Long-running SSE termination requires staging observation.
3. Queue depth and database-pool saturation require target-size telemetry.
4. Backup RPO depends on the external schedule; CI proves integrity and restorability only.
5. The release owner must inspect the artifacts and approve the final decision.

## Promotion rule

Do not promote to `development` or create an RC tag when any mandatory check is red, cancelled, unexpectedly skipped or based on a superseded commit.
