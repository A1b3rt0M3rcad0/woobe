# Accepted Run identity

Agent and Network responses expose `runtime_identity` derived from the durable accepted snapshot, including historical completed Runs. Recovery reconstructs it from persisted admission data, never from current Production. Missing historical snapshots report unavailable provenance instead of inventing an origin.

Standalone Agent Sessions follow the selected environment between Runs (`follow_selection_between_runs`). Network Sessions pin their native Network version (`pinned_session_version`); constituent Agents and exact Candidates retain their accepted snapshots. Changing Production does not rewrite a Network Session. Start a new Session to adopt the new version.

`agent-run-admission@1` hashes the complete accepted Agent snapshot. `agent-run-binding-revisions@1` identifies admitted provider credential references and revision timestamps, without secret values. `network-run-admission@1` hashes the captured native definition and bindings, excluding observational `asac_run_identity` metadata: the same pinned executable closure keeps its digest after environment selection changes. Publication evidence and selection/deployment identity remain separate observations, captured at admission. Ambiguous native publication origins report `publication_ambiguous`; no arbitrary lineage is selected.

Knowledge candidate bindings include the embedding Model identity, immutable specification hash, Model revision and provider credential revision. Activation rechecks active status, scope, revision and authority under locks. Credential rotation or Model changes invalidate stale plans.

Published snapshot evidence is not a claim about live external responses. Referenced credentials, Knowledge stores, providers and external Tools can change or become unavailable. Admission digests record accepted references, not reproducible remote content. Runtime Keys continue to enforce their native resource, Project and environment boundary.

For CLI continuation use YAML `session_id: UUID` (or `options.session_id`). Unknown fields and conflicting aliases are rejected; omitting Session identity intentionally starts a new Session. See the CLI runtime help for the exact input schema.
