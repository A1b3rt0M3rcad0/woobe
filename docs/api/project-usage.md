# Project Usage API

`GET /metering/projects/{project_id}/usage`

The Project Usage endpoint is the FinOps-oriented read model for runtime consumption. It is distinct from Project Overview:

- Overview answers whether the Project is operating correctly.
- Usage explains what consumed resources, how much known provider spend was generated, and which dimensions drove it.

Shared request and cost metrics use terminal traces as the canonical source so the same Project, interval and environment reconcile with Overview.

## Query parameters

| Parameter | Values | Default |
|---|---|---|
| `from` | ISO-8601 with UTC offset | 30 days before `to` |
| `to` | ISO-8601 with UTC offset | current time |
| `bucket` | `hour`, `day` | inferred from range |
| `environment` | `all`, `draft`, `staging`, `production` | `all` |
| `agent_id` | UUID | none |
| `provider_model_id` | UUID | none |
| `release_id` | UUID | none |
| `group_by` | `agent`, `model`, `provider`, `environment`, `release` | `agent` |
| `top_limit` | 1-50 | 10 |

The interval is half-open: `[from, to)`. The maximum range is 90 days. Hourly buckets are limited to seven days.

## Metric semantics

- `runtime_requests`: terminal executions (`completed`, `failed`, `cancelled`).
- `llm_calls`: individual provider calls inside those executions.
- `known_cost_usd`: the sum of known pricing snapshots. Unknown pricing is never converted to a known zero.
- `priced_requests`: executions with `cost_status=known`.
- `partial_cost_requests`: executions with some known and some unknown cost.
- `unpriced_requests`: executions without complete pricing.
- `cost_coverage_percent`: fully priced requests divided by runtime requests.
- `cost_per_priced_request`: known spend divided by fully priced requests.
- `failed_spend_usd`: known spend attached to failed or cancelled executions.

One runtime request may contain multiple LLM calls, tool calls and fallback calls.

## Spend wording

The API reports estimated provider spend. It does not represent a Woobe invoice or customer billable amount. This distinction is required while Projects use customer-managed provider credentials.

## Data freshness

`data_through` is the latest terminal execution included in the response. `data_quality.aggregation_lag_seconds` reports the age of that execution relative to response generation.

## Legacy data

Historical traces that predate release, model or environment attribution remain visible. Missing dimensions are returned as unattributed instead of being inferred from current mutable Agent state.
