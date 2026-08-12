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
- `recent_limit`: maximum number of recent changes, releases, Agent Runs, and Network Runs. Integer from 1 to 20, default 5.

The maximum supported range is 30 days. Hour buckets are limited to seven days. Invalid timestamps, reversed ranges, unsupported buckets, unsupported environments, and excessive ranges return HTTP 422.

The frontend keeps a stable query identity per Project, environment, and range. The rolling `from` and `to` values are calculated at request time so background refreshes update the interval without replacing the entire page with a new initial-loading state.

## Operational definitions

### Agent Run

An Agent Run represents one execution of one Agent. Direct Runtime API, Playground, Job, and Network-invoked executions are counted as Agent Runs. Session is optional and does not define whether the Run exists.

The following invariant must always hold:

`agent_runs = direct_agent_runs + network_agent_runs`

All three fields are calculated from the same persisted Agent execution source. Network invocations may be used for Network composition metrics, but they must not overwrite the Agent Run breakdown.

The current read model derives Agent Run metrics from persisted execution traces while keeping Trace as a diagnostic concept in the UI. The compatibility fields based on `requests` remain available temporarily for older consumers.

### Network Run

A Network Run represents one execution of one Network and is read directly from `network.network_executions`. Its internal Agent executions are measured from Network invocations and Agent execution traces. Agent Run and Network Run counts are not additive business totals because a Network Run contains Agent Runs.

### Terminal Runs and reliability

Running, queued, pending, processing, and cancellation-requested Runs do not enter reliability denominators.

Agent Run success rate is:

`successful_agent_runs / terminal_agent_runs`

Agent Run error rate is:

`(failed_agent_runs + timed_out_agent_runs) / terminal_agent_runs`

Network Run success rate is:

`successful_network_runs / terminal_network_runs`

Network Run error rate is:

`(failed_network_runs + timed_out_network_runs + uncertain_network_runs) / terminal_network_runs`

Cancelled Runs are shown separately and are not automatically classified as system errors. When there are no terminal Runs, success and error rates are `null`, not zero or one hundred percent.

### Cost

Project runtime cost is the sum of known Agent Run costs. Network Run cost is an aggregation of its Agent Runs and must not be added again to the Project total.

A recent Network Run returns:

- `cost_usd`: known subtotal, or `null` when no Agent Run cost is known;
- `cost_known`: true only when every recorded Agent Run has known cost;
- `priced_agent_runs`;
- `total_agent_runs`;
- `unknown_cost_count`.

This allows the UI to display a known partial subtotal without presenting it as a complete cost.

## Environment semantics

Network Agent Runs inherit the environment of the persisted Network Session. Direct Agent Runs use the execution context recorded at runtime: Production, Staging, or Draft for Playground. Legacy records without runtime context fall back to the current Agent release slot.

`playground` is an execution source, not an environment. Playground executions are returned as:

- environment: `draft`;
- source: `playground`.

## Summary metrics

### Agent Runs

- `agent_runs`: all Agent executions started in the requested window.
- `direct_agent_runs`: Agent Runs without a Network execution.
- `network_agent_runs`: Agent Runs associated with a Network execution.
- `terminal_agent_runs`: completed, failed, timed-out, or cancelled Agent Runs.
- `successful_agent_runs`: completed Agent Runs.
- `completed_with_issues_agent_runs`: reserved for an explicit persisted status; currently zero when no such status exists.
- `failed_agent_runs`: failed Agent Runs excluding timeout-classified failures.
- `timed_out_agent_runs`: failed Agent Runs with explicit timeout evidence.
- `cancelled_agent_runs`: cancelled Agent Runs.
- `running_agent_runs`: pending, queued, running, or processing Agent Runs.
- `agent_run_change_percent`: percentage change versus the immediately preceding equal window.
- `avg_agent_run_duration_ms`: average duration of terminal Agent Runs with known duration.
- `p95_agent_run_duration_ms`: continuous p95 duration of terminal Agent Runs.
- `agent_run_success_rate` and `agent_run_error_rate`.
- `agent_run_cost_usd`: sum of known terminal Agent Run costs.
- `priced_agent_runs` and `unknown_agent_run_cost_count`.

### Network Runs

- `network_runs`: Network executions accepted in the requested window.
- `terminal_network_runs` and `successful_network_runs`.
- `failed_network_runs`, `timed_out_network_runs`, `uncertain_network_runs`, and `cancelled_network_runs`.
- `running_network_runs`: queued, running, or cancellation-requested Network Runs.
- `network_run_success_rate` and `network_run_error_rate`.
- `avg_network_run_duration_ms` and `p95_network_run_duration_ms`.
- `avg_agent_runs_per_network_run`: average persisted Network invocations per non-queued Network Run.

### Compatibility fields

`requests`, `request_change_percent`, `avg_latency_ms`, `p95_latency_ms`, `success_rate`, `failed_requests`, `cost_usd`, and `unknown_cost_count` remain in the response for transitional compatibility. New consumers must use the Run-oriented fields.

## Timeseries

Every requested bucket is returned, including empty buckets. Each point separates:

- Agent Run volume, success, failed, timed out, cancelled, running, success rate, average duration, and p95 duration;
- Network Run volume, success, failed, timed out, uncertain, cancelled, running, success rate, and average duration;
- tokens, known Agent Run cost subtotal, and unknown cost count.

Bucket boundaries are calculated in UTC. `from` is inclusive and `to` is exclusive.

## Changes in the selected context

`recent_changes` is a chronological, environment-aware timeline with:

- resource type and identity;
- environment;
- action;
- version or Draft revision;
- description;
- occurrence timestamp;
- whether the change is immutable.

The environment filter changes the semantics:

- `draft`: mutable Agent Draft snapshots and Network `draft_revision` updates;
- `staging`: Agent releases and Network versions published to Staging;
- `production`: immutable releases, rollbacks, and reactivations;
- `all`: all of the above in one chronological list.

Draft activity is never labeled as a release. The read model reports the latest persisted Draft mutation timestamp available in the selected window; it does not fabricate a complete audit history.

`recent_releases` and `recent_network_releases` remain available for compatibility with existing consumers.

## Recent Runs

- `recent_traces`: lightweight **direct Agent Runs only**. Agent Runs internal to a Network are intentionally excluded from the Overview list.
- `recent_network_runs`: primary Network Runs with duration and cost completeness.

The frontend merges both sources, sorts by start time, and displays at most the three latest primary executions. Internal Agent Runs are inspected inside the Network Run detail.

## Operational issues

`operational_issues` is a bounded aggregate containing:

- up to three Agents with the most failed Runs;
- up to three Networks with the most failed, timed-out, or uncertain Runs;
- up to five failure codes;
- the bucket with the highest combined error count.

The Overview does not return full error payloads or perform AI-generated root-cause analysis.

## Current Project state

- `environment_distribution`: current Agent counts for Draft, Staging, and Production.
- `knowledge_summary`: current Project-wide Collection and active Document counts, indexing health, and storage.
- `tools_summary`: current Project-wide Tool state and recent Tool failures.
- `capabilities`: panels without dedicated read models remain disabled instead of displaying fabricated data.

Knowledge and Tool summaries are current Project-wide state. They are not historical environment snapshots.

## Authorization and caching

Project authorization is completed before the read-model repository runs. Every query also includes `project_id` explicitly. Responses use `Cache-Control: private, max-age=15` and `Vary: Authorization`; shared caches must not reuse data across tenants.

## Performance target

The read model must execute a bounded number of aggregate queries independent of Agent count. The acceptance target remains p95 below 500 ms without network latency for a representative local PostgreSQL fixture covering 30 days. Agent Run queries must use the Project/time trace index, and Network Run queries must use the Project/status/time execution indexes.
