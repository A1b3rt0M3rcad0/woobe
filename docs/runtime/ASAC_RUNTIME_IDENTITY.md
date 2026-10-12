# Accepted Run identity

Agent and Network responses expose `runtime_identity` derived from the durable accepted snapshot, including historical completed Runs. Recovery reconstructs it from persisted admission data, never from current Production. Missing historical snapshots report unavailable provenance instead of inventing an origin.

Standalone Agent Sessions follow the selected environment between Runs (`follow_selection_between_runs`). Network Sessions pin their native Network version (`pinned_session_version`); constituent Agents and exact Candidates retain their accepted snapshots. Changing Production does not rewrite a Network Session. Start a new Session to adopt the new version.

`agent-run-admission@1` hashes the complete accepted Agent snapshot. `agent-run-binding-revisions@1` identifies admitted provider credential references and revision timestamps, without secret values. `network-run-admission@1` hashes the captured native definition and bindings, excluding observational `asac_run_identity` metadata: the same pinned executable closure keeps its digest after environment selection changes. Publication evidence and selection/deployment identity remain separate observations, captured at admission. Ambiguous native publication origins report `publication_ambiguous`; no arbitrary lineage is selected.

Knowledge candidate bindings include the embedding Model identity, immutable specification hash, Model revision and provider credential revision. Activation rechecks active status, scope, revision and authority under locks. Credential rotation or Model changes invalidate stale plans.

Published snapshot evidence is not a claim about live external responses. Referenced credentials, Knowledge stores, providers and external Tools can change or become unavailable. Admission digests record accepted references, not reproducible remote content. Runtime Keys continue to enforce their native resource, Project and environment boundary.

For CLI continuation use YAML `session_id: UUID` (or `options.session_id`). Unknown fields and conflicting aliases are rejected; omitting Session identity intentionally starts a new Session. See the CLI runtime help for the exact input schema.


## Frozen model pricing

New legacy-compatible ModelSpecs retain their configured prices alongside model
capabilities. Runtime metering reads primary and fallback pricing from the exact
frozen ModelSpec, including portable/imported Models with no native ProviderModel
ID. It never substitutes mutable catalog prices for missing frozen pricing.
Older frozen specs may contain pricing in their frozen source metadata; this
compatibility source is read without consulting today's ProviderModel. Immutable
snapshots without any frozen pricing remain unpriced. Historical Run rows and
receipts are not recalculated or rewritten.

USD cost is known only with complete, nonnegative integer token usage and both
finite, nonnegative rates. Zero is a valid price. Canonical `*_cost_per_1m_tokens`
rates declare their unit explicitly; generic input/output rates accept declared
`per_token`, `per_1k_tokens` or `per_1m_tokens`, normalized to per-million rates.
Unsupported billing units, non-USD currency (no implicit FX conversion), absent
rates or invalid rates produce unknown pricing; incomplete token usage produces
unknown tokens. Overview retains unknown/partial coverage rather than presenting
unpriced Runs as zero cost. Configure prices on the Model before capturing a new
Candidate/Release if future immutable Runs need known costs.

The operational Overview aggregates the recorded `AgentRun.usage`, environment
and Network execution identity. A matching observability trace is not counted a
second time and cannot replace an unknown accepted cost with a stale value.
Historical traces without an Agent Run remain readable for compatibility.
Network cost is the known subtotal of its terminal constituent Agent Runs;
coverage remains partial when any constituent is unpriced. Reads do not reprice
or rewrite Runs or traces.

`unknown_pricing_agent_runs` and `unknown_token_usage_agent_runs` distinguish
missing frozen prices from incomplete provider usage in the Overview summary.
Recent direct Runs expose `cost_status` and `cost_reason`. To resolve missing
pricing for future Runs, open **Models → Model → Pricing**, configure both input
and output USD rates per million tokens (zero is allowed), save, then capture,
evaluate, publish and deploy a new Candidate/Release. Changing the Model alone
does not alter a previously published Release. Non-USD prices require explicit
conversion outside runtime metering; Woobe does not assume an exchange rate.

See [Web selection](ASAC_HISTORY.md#web-environment-selection) and the
[acceptance matrix](../testing/ASAC_ACCEPTANCE.md).
