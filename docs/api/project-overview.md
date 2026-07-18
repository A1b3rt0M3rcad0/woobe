# Project overview read model

## Endpoint

`GET /core/projects/{project_id}/overview`

The endpoint returns one authorized, tenant-scoped operational read model for the Project Overview. The public language is based on **Agent Runs** and **Network Runs**. Traces remain diagnostic evidence and are not presented as the primary business unit.

All timestamps are UTC ISO 8601 values. The response is aggregate-only and never includes provider credentials, API keys, prompts, document content, Tool configuration, full trace payloads, or user-identifying fields.

## Query parameters

- `from`: inclusive UTC timestamp. Defaults to `to - 24 hours`.
- `to`: exclusive UTC timestamp. Defaults to the current UTC time.
- `bucket`: `hour` or `day`. Defaults to `hour` for ranges up to 48 hours and `day` otherwise.
- `environment`: `all`, `draft`, `staging`, or `production`. Defaults to `all`.
- `recent_limit`: maximum number of recent releases, Agent Runs, and Network Runs. Integer from 1 to 20, default 5.

The maximum supported range is 30 days. Hour buckets are limited to seven days. Invalid timestamps, reversed ranges, unsupported buckets, unsupported environments, and excessive ranges return HTTP 422.

## Operational definitions

### Agent Run

An Agent Run represents one execution of one Agent. Direct Runtime API, Playground, Job, and Network-invoked executions are counted as Agent Runs. Session is optional and does not define whether the Run exists.

The current read model derives Agent Run metrics from persisted execution traces while keeping Trace as a diagnostic concept in the UI. The compatibility fields based on `requests` remain available temporarily for older consumers.

### Network Run

A Network Run represents one execution of one Network and is read directly from `network.network_executions`. Its internal Agent executions are measured from Network invocations and Agent execution traces. Agent Run and Network Run counts are not additive business totals because a Network Run contains Agent Runs.

### Cost

Project runtime cost is the sum of known Agent Run costs. Network Run cost is an aggregation of its Agent Runs and must not be added again to the Project total.

## Environment semantics

Each Agent is assigned one current environment from its latest active release slot:

- latest status `production` -> `production`;
- latest status `staging` -> `staging`;
- latest status `draft`, archived states, or no release -> `draft`.

`playground` is an execution source, not an environment. Existing trace records that historically expose `playground` are normalized by consumers to Draft plus Playground source.

## Summary metrics

### Agent Runs

- `agent_runs`: all Agent executions started in the requested window.
- `direct_agent_runs`: Agent Runs without a Network execution.
- `network_agent_runs`: Agent Runs associated with a Network execution.
- `running_agent_runs`: Agent Runs in pending, queued, running, or processing states.
- `failed_agent_runs`: failed or cancelled Agent Runs.
- `agent_run_change_percent`: percentage change versus the immediately preceding equal window.
- `avg_agent_run_duration_ms`: average duration of terminal Agent Runs with known duration.
- `p95_agent_run_duration_ms`: continuous p95 duration of terminal Agent Runs.
- `agent_run_success_rate`: completed divided by terminal Agent Runs.
- `agent_run_cost_usd`: sum of known terminal Agent Run costs.
- `unknown_agent_run_cost_count`: terminal Agent Runs without consolidated cost.

### Network Runs

- `network_runs`: Network executions accepted in the requested window.
- `running_network_runs`: queued, running, or cancellation-requested Network Runs.
- `failed_network_runs`: failed, timed out, uncertain, or cancelled Network Runs.
- `network_run_success_rate`: completed divided by terminal Network Runs.
- `avg_network_run_duration_ms`: average completed Network Run duration.
- `p95_network_run_duration_ms`: continuous p95 completed Network Run duration.
- `avg_agent_runs_per_network_run`: average persisted Network invocations per non-queued Network Run.

### Compatibility fields

`requests`, `request_change_percent`, `avg_latency_ms`, `p95_latency_ms`, `success_rate`, `failed_requests`, `cost_usd`, and `unknown_cost_count` remain in the response for transitional compatibility. New consumers must use the Run-oriented fields.

## Timeseries

Every requested bucket is returned, including empty buckets. Each point separates:

- Agent Run volume, success, failures, average duration, and p95 duration;
- Network Run volume, success, failures, and average duration;
- tokens, known cost subtotal, and unknown cost count.

Bucket boundaries are calculated in UTC. `from` is inclusive and `to` is exclusive.

## Recent activity

- `recent_traces`: lightweight Agent execution records consumed as recent Agent Runs; Trace details remain diagnostic evidence.
- `recent_network_runs`: Network Run identity, Network, environment, status, duration, root trace, and timestamps.
- `recent_releases`: minimal Agent release identity, environment, version, and timestamps.

The frontend merges recent Agent Runs and Network Runs into one Recent Runs timeline and navigates to the corresponding Agent Playground or Network workspace.

## Other sections

- `environment_distribution`: current Agent counts for Draft, Staging, and Production.
- `knowledge_summary`: Collection and active Document counts, indexing health, and storage.
- `tools_summary`: Tool state and recent failures when real execution evidence exists.
- `capabilities`: panels without dedicated read models remain disabled instead of displaying fabricated data.

## Authorization and caching

Project authorization is completed before the read-model repository runs. Every query also includes `project_id` explicitly. Responses use `Cache-Control: private, max-age=15` and `Vary: Authorization`; shared caches must not reuse data across tenants.

## Performance target

The read model must execute a bounded number of aggregate queries independent of Agent count. The acceptance target remains p95 below 500 ms without network latency for a representative local PostgreSQL fixture covering 30 days. Agent Run queries must use the Project/time trace index, and Network Run queries must use the Project/status/time execution indexes.
