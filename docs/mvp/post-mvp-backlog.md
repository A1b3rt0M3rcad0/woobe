# Post-MVP backlog

This file contains non-blocking work intentionally excluded from the MVP release-hardening branch. Confirmed P0 and P1 findings remain release blockers and cannot be deferred here.

## P2

- distributed load against a production-sized PostgreSQL pool and RabbitMQ cluster;
- scheduled restore drills with historical RPO/RTO reporting;
- multi-browser coverage after Chromium qualification is stable;
- enforced vulnerability thresholds after the first scanner baseline is approved;
- long-running SSE termination telemetry from staging;
- queue-depth and database-pool saturation dashboards for release rehearsals.

## P3

- visual-regression snapshots for dashboard and playground;
- additional deterministic provider-chaos profiles;
- trend reports for image size, p95 latency and TTFT;
- browser accessibility audits and performance budgets;
- expanded operational game days for dependency outages.

## Deferral rules

- tenant isolation, authentication, migration, rollback and core-flow regressions are release blockers;
- deferred items require an owner before entering a scheduled release;
- this backlog does not authorize release and is subordinate to `release-readiness-report.md`.
