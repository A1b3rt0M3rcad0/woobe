# Project overview read model

## Endpoint

`GET /core/projects/{project_id}/overview`

The endpoint returns one authorized, tenant-scoped read model for the dashboard. All timestamps are UTC ISO 8601 values. The response is intentionally aggregate-only and never includes provider credentials, API keys, prompts, document content, tool configuration, trace payloads, or user-identifying fields.

## Query parameters

- `from`: inclusive UTC timestamp. Defaults to `to - 24 hours`.
- `to`: exclusive UTC timestamp. Defaults to the current UTC time.
- `bucket`: `hour` or `day`. Defaults to `hour` for ranges up to 48 hours and `day` otherwise.
- `environment`: `all`, `draft`, `staging`, or `production`. Defaults to `all`.
- `recent_limit`: maximum number of recent releases and traces. Integer from 1 to 20, default 5.

The maximum supported range is 30 days. Hour buckets are limited to seven days. Invalid timestamps, reversed ranges, unsupported buckets, unsupported environments, and excessive ranges return HTTP 422.

## Environment semantics

Each agent is assigned one current environment from its latest release ordered by `COALESCE(promoted_at, created_at)` and then `created_at`:

- latest status `production` -> `production`;
- latest status `staging` -> `staging`;
- latest status `draft`, `archived`, `rolled_back`, or no release -> `draft`.

The environment filter applies to request metrics, timeseries, recent traces, and active agent count. `production_agents` always reports the total number of agents currently assigned to production in the project.

## Summary metric definitions

- `active_agents`: agents with status `active`, restricted by the requested environment when one is selected.
- `production_agents`: agents whose current environment is production.
- `requests`: terminal traces in the requested window. Terminal states are `completed`, `failed`, and `cancelled`.
- `request_change_percent`: percentage change versus the immediately preceding window of equal duration. It is `0` when both windows have zero requests and `null` when the previous window is zero but the current window is non-zero.
- `avg_latency_ms`: average `total_latency_ms` across terminal traces with known latency.
- `p95_latency_ms`: PostgreSQL continuous percentile 0.95 across terminal traces with known latency.
- `success_rate`: `completed / (completed + failed + cancelled) * 100`. It is `null` when there are no terminal traces.
- `failed_requests`: traces with status `failed` or `cancelled`.
- `cost_usd`: sum of known trace costs. It is `0` for an empty window, `null` when requests exist but every cost is unknown, and the known subtotal when known and unknown costs coexist.
- `unknown_cost_count`: terminal traces whose `total_cost_usd` is null.

Pending and running traces are excluded from terminal metrics.

## Timeseries definitions

Every requested bucket is returned, including empty buckets. Each point contains:

- `requests`, `success`, and `failed` using the terminal-state definitions above;
- `avg_latency_ms` and `p95_latency_ms` for known latency values;
- `input_tokens` and `output_tokens` from persisted trace execution data;
- `cost_usd`, which is null when a non-empty bucket contains only unknown costs;
- `unknown_cost_count`.

Bucket boundaries are calculated in UTC. `from` is inclusive and `to` is exclusive.

## Other sections

- `environment_distribution`: current agent counts for draft, staging, and production.
- `recent_releases`: minimal release identity, agent, environment, version, and timestamps.
- `recent_traces`: minimal trace identity, agent, environment, terminal status, latency, token total, known cost, and start time.
- `knowledge_summary`: collection count, document count, indexed, failed, pending, and total stored bytes.
- `tools_summary`: total, active, inactive, and up to five recent failed tool executions when trace events provide a real source.
- `capabilities`: `sessions_jobs`, `ingestion_pipeline`, and `activity_feed` remain `false` until dedicated read models exist. Consumers must hide or mark those panels unavailable rather than inventing data.

## Authorization and caching

Project authorization is completed before the read-model repository runs. Every query also includes `project_id` explicitly. Responses use `Cache-Control: private, max-age=15` and `Vary: Authorization`; shared caches must not reuse data across tenants.

## Performance target

The repository executes a constant number of aggregate queries independent of agent count. The acceptance target is p95 below 500 ms without network latency for a representative local PostgreSQL fixture covering 30 days of traces. Query plans for the summary/timeseries query must use the project/time trace index once the fixture is large enough for the planner to prefer it.
