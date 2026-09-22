# Context evidence and observability

Programmable Context Managers must remain explainable. The shared Runtime records a `ContextSnapshot` for every instrumented Model Invocation.

## ContextSnapshot

A Snapshot captures the effective materialization decision, including:

~~~text
project_id
agent_run_id
model_invocation_id
policy schema/hash
model capacity
reserved output
runtime reserve
usable input budget
estimated/reported input units
utilization
pressure status
measurement status
materialized hash
retention mode
reproduction level
contributions
manifest
~~~

The Manager does not construct this object directly.

## ContextContribution

Each materialized contribution records evidence such as:

~~~text
source_type
source_ref
parent_ref
modality
priority
raw_units
materialized_units
selection_method
relevance_score
transformations
trust
sensitivity
integrity_hash
metadata
~~~

This lets observability answer not only "how many tokens were used?" but "what kind of context was selected, transformed or excluded, and why?"

## Manifest metrics

Current Runtime metrics include:

~~~text
raw_candidate_count
raw_candidate_units
selected_count
selected_raw_units
selected_units
selection_ratio
compaction_ratio
compaction_saving_units
truncation_count
truncation_rate
configured_input_budget_units
model_usable_input_units
effective_input_budget_units
budget_clamped
pre_budget_units
budget_reduction_units
context_preservation_ratio
headroom_units
headroom_ratio
context_fit_status
~~~

## Exclusion evidence

Excluded candidates are summarized by source and reason.

Current reasons include:

~~~text
source_not_allowed
session_window
deduplicated
source_cap
source_cap_unrepresentable
global_budget
global_budget_unrepresentable
~~~

A new Runtime primitive that removes or transforms context should add evidence rather than silently changing the prompt.

## Transformation evidence

Current transformations include deterministic truncation and upstream Tool compaction.

A future semantic-summary primitive must add explicit transformation/provenance fields such as `semantic_summary` and source lineage.

## Measurement semantics

Text and structured data use Woobe's conservative input-unit estimator before provider usage is known.

For opaque/multimodal payloads, Runtime does not pretend every modality is exactly token-comparable. Snapshot measurement status becomes `PARTIAL` where appropriate.

Provider-reported usage may later enrich the Snapshot and replace estimated pressure/utilization with reported values.

## Why this matters for custom Managers

A custom Manager may choose a radically different selection algorithm while still producing comparable operational evidence.

The invariant is:

> algorithm diversity must not destroy runtime observability.
