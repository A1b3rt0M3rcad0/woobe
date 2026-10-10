# Qualified Agent and Network delivery

The Woobe CLI's unified `deploy` command orchestrates the existing owner
contracts. It does not deploy this server or introduce a second lifecycle engine.
The backend remains the authority for target/Project permissions, managed policy,
qualification, binding generations, environment CAS, database-clock leases,
fencing and atomic selection/receipt/outbox commit.

```sh
woobe agent AGENT_UUID deploy --from release --release RELEASE_UUID --notes 'Approved delivery' --yes
woobe network NETWORK_UUID deploy --from staging --notes 'Promote qualified Staging' --yes
woobe agent '@support' deploy --from local --suite tests/evaluation.yaml --notes 'Deliver validated author source' --yes
```

Release mode needs no local development registry. Staging mode captures an exact
immutable ASaC Release/generation and refuses drift; legacy snapshots are not
silently republished. Local mode starts from an accepted registered source,
seals an immutable Revision and uses an isolated intent Draft, exact Candidate,
passed Evaluation and Publication before deploying. Agent and Network follow
identical public syntax, preserving Network constituent snapshots.

`--via-staging --smoke FILE` requires explicit assertions and a separate Runtime
Key. Failed/uncertain smoke keeps Staging and blocks Production. CLI Key authority
never becomes Runtime authentication. Rollback selects an explicit previously
qualified Release with `--action rollback`, creating a new audited transition.
No inference of latest, automatic rollback, cross-instance transfer or implicit
native resource creation is included.

## Production-only CI identity

Create a dedicated Control Key with target-scoped `agent:production` or
`network:production`, plus authorized reads of the target and frozen dependencies.
To promote Staging, permit reads of Staging as well as Production; the absence
of `:version` still denies Staging writes/publication. Keep `:write`, key/policy
management and Provider secrets out of the deploy-only job.

Enable managed Project lifecycle policy and explicitly allow its stable
`control:CONTROL_KEY_ID` actor in `production_actors`. An actor entry does not
create grants. Author/deploy credentials remain separate; legacy promotion cannot
bypass managed gates. Operators configure protected GitHub Environments, reviewed
branches and secrets. See the CLI's [deployment guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/DEPLOYMENT.md)
and [pinned CI example](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/CI_DEPLOYMENT.md).

## Original-operation recovery

The CLI retains a private intent journal before writes. Each step has a stable
operation UUID scoped to instance, Workspace, Project, resource kind and target.
Resume reads original committed operations and validates receipts/current before
continuing. Missing journal, 404/not_observed, changed actor/input or forged
receipt never authorizes a replay. CI must restore the original encrypted/private
checkpoint; the official example blocks retries when it is absent.

The existing owners retain immutable Revision/Candidate/Evaluation/Publication,
deployment and operation evidence. No new ledger or permission category is
needed for this delivery. Operation recovery accepts an explicit environment
filter (`asac.operation_environment_reads`); the owner checks the persisted
receipt environment again before returning it. Deployment/lease recovery therefore
needs no Draft grant. A forged filter cannot reveal a receipt from another
environment or actor. A failed apply preserves the published Release. A
committed apply with incomplete observation reports that uncertainty rather than
claiming rollback or failure erased its effect. Leases are acquired close to
apply; stale/expired evidence remains rejected under owner CAS.

## Acceptance and limits

`tests/integration/cli/unified_deployment.py` is invoked from the existing compiled
CLI/API/PostgreSQL contract for both resource kinds. It exercises clean UUID
preflight/delivery, local qualification, exact Staging promotion, rollback,
Production Runtime identity, deployment row uniqueness after truncated committed
response, managed actor denial/allowance, deploy-only grants and negative Staging
smoke. Existing owner tests retain the concurrency, revoked binding, policy drift,
fencing, signed receipt and admitted-Session boundaries.

This repeatable contract uses disposable test resources and deterministic
provider workers. It does not qualify an operator's Production configuration,
external provider reliability, a multi-machine load benchmark or protected
Environment settings. Git provenance/signature verification remains an independent
existing gate; deployment does not manufacture provenance from a workflow URL.
