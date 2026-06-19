# MVP Stage 05 completion

Status: implementation complete; merge remains gated by the final GitHub Actions result on the branch head.

Delivered:

- authorized `GET /core/projects/{project_id}/overview` endpoint;
- deterministic 24-hour, 7-day, and 30-day metric semantics;
- current-environment filtering for draft, staging, and production agents;
- terminal trace metrics, timeseries, releases, knowledge, tools, and explicit unavailable capabilities;
- tenant-scoped queries and private response caching;
- CoreUnitOfWork integration using one request transaction;
- explicit UTC bucket boundaries independent of the PostgreSQL session timezone;
- partial indexes for terminal traces and tool-call events;
- deterministic PostgreSQL integration fixtures covering aggregation, isolation, environment filtering, null costs, terminal states, query count, timezone handling, index eligibility, and the 30-day p95 target.

Merge gate:

1. migrations, backend, frontend, and container workflows must pass on the final head;
2. the PR must no longer be a draft;
3. the PR description must include validation and rollback evidence;
4. no new baseline regression is permitted.
