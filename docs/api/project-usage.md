# Project Usage API

`GET /metering/projects/{project_id}/usage`

The Project Usage endpoint is the FinOps read model for runtime operations. It is distinct from Project Overview:

- Overview answers whether the Project is operating correctly.
- Usage explains how much the operation cost, how many Agent Runs and Network Runs occurred, and which dimensions produced that cost.

The public operational units are **Agent Run** and **Network Run**. Trace is diagnostic evidence and is not the accounting unit.

## Query parameters

| Parameter | Values | Default |
|---|---|---|
| `from` | ISO-8601 with UTC offset | 30 days before `to` |
| `to` | ISO-8601 with UTC offset | current time |
| `bucket` | `hour`, `day` | inferred from range |
| `environment` | `all`, `draft`, `staging`, `production` | `all` |
| `operation` | `all`, `agent`, `network` | `all` |
| `network_id` | UUID | none |
| `agent_id` | UUID | none |
| `provider_model_id` | UUID | none |
| `release_id` | UUID | none |
| `group_by` | `agent`, `network`, `model`, `provider`, `environment`, `release` | `agent` |
| `top_limit` | 1-50 | 10 |

The interval is half-open: `[from, to)`. The maximum range is 90 days. Hourly buckets are limited to seven days.

## Operation semantics

- `all`: all Agent Runs and all Network Runs in the selected scope.
- `agent`: direct Agent Runs only. Agent Runs contained by Networks and Network Runs are excluded.
- `network`: Network Runs and the Agent Runs contained by them.

The `network_id`, `agent_id`, model and release filters constrain attribution inside the selected operation. Provider and Model are supporting cost dimensions, not the primary operational unit.

## Agent Run

An Agent Run is one logical execution of one Agent. Direct runtime calls and Agent executions inside Networks are both Agent Runs.

The endpoint returns:

- `agent_runs`;
- `direct_agent_runs`;
- `network_agent_runs`;
- success, failure and cancellation counts;
- known cost and pricing coverage;
- average, median and p95 unit-cost metrics where applicable.

The invariant is:

`agent_runs = direct_agent_runs + network_agent_runs`

The current MVP projection derives Agent Runs from persisted execution traces, matching the Project Overview. Trace remains subordinate in the product language and is exposed only as a diagnostic reference.

## Network Run

A Network Run is one execution of one Network. It is read from `network.network_executions`.

Its cost is the known subtotal of the Agent Runs related to that Network Run. Network cost is therefore an attribution view contained in total Agent Run cost.

Do not calculate:

`project_cost = agent_run_cost + network_run_cost`

The correct project total is:

`project_cost = sum(agent_run_cost)`

`network_run_cost` answers how much of that total was caused by Network operations.

The endpoint also returns:

- `network_runs`;
- success, failure and cancellation counts;
- `avg_agent_runs_per_network_run`;
- known, partial and unpriced Network Runs;
- average, median and p95 Network Run cost.

## Cost semantics

- `known_cost_usd`: sum of known Agent Run cost. This is the Project runtime cost for the selected scope.
- `network_run_cost_usd`: subset of known cost attributed to Network Runs.
- `failed_spend_usd`: known cost attached to failed or cancelled Agent Runs.
- `cost_per_priced_agent_run`: known Agent Run cost divided by fully priced Agent Runs.
- `cost_per_priced_network_run`: fully priced Network Run cost divided by fully priced Network Runs.
- `median_*` and `p95_*`: unit-cost distribution metrics for investigating long-tail cost.

Unknown pricing is never converted into a known zero. When Runs exist but none has known cost, the corresponding cost is `null`. When some Runs are priced and others are not, the endpoint returns a known subtotal plus explicit coverage counters.

## Timeseries

Every requested bucket is returned, including empty buckets. Each point distinguishes:

- Agent Runs;
- direct Agent Runs;
- Agent Runs inside Networks;
- Network Runs;
- Agent Run cost;
- Network-attributed cost;
- cost per Agent Run and Network Run;
- tokens and LLM calls.

Network cost remains contained in Agent Run cost in every bucket.

## Breakdown

Breakdown rows always attribute cost from Agent Runs. Supported dimensions are:

- Agent;
- Network;
- Provider;
- Model;
- Environment;
- Release.

A Network row aggregates the Agent Runs produced by that Network. Direct Agent Runs are represented by a separate `Direct Agent Runs` row when the active operation includes them.

## Most expensive Runs

`top_executions` returns direct Agent Runs and Network Runs. Internal Agent Runs are represented by their parent Network Run in this list to avoid duplicate operational rows.

Each item includes:

- `run_id` and `run_type`;
- target Agent or Network;
- status and environment;
- duration;
- LLM, token and Tool consumption;
- Agent Run count for Network Runs;
- known, partial or unknown cost status;
- optional Trace reference for diagnostics.

## Compatibility fields

The response temporarily preserves `runtime_requests`, `successful_requests`, `failed_requests`, `priced_requests` and related fields. They are exact aliases of Agent Run metrics and are deprecated for new consumers.

## Data freshness

`data_through` is the latest terminal Agent Run or Network Run included in the response. `data_quality.aggregation_lag_seconds` reports its age relative to response generation.
