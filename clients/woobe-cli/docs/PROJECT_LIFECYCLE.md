# Project lifecycle policy

A compatible Woobe backend owns lifecycle authority. Inspect it with:

```sh
woobe project lifecycle show
```

An absent policy is explicitly `managed: false`, generation `0`. A managed
Project requires exact Candidate evaluation/publication and fenced deployment;
legacy Agent/Network promotion cannot bypass the server gate. Read-only history
and already admitted Runs remain available. Policy does not grant permissions.

Changing policy requires `project:access:write`, a stable operation UUID,
expected current generation and an audit reason. Prepare `lifecycle-policy.yaml`:

```yaml
operation_id: 550e8400-e29b-41d4-a716-446655440000
expected_generation: 0
managed: true
production_actors: []
reason: Require evaluated publication and explicit deployment
```

Replace the operation UUID for each **new** policy change and read the current
generation before submitting. Keep the exact original UUID/body for recovery.

```sh
woobe project lifecycle update --file lifecycle-policy.yaml --validate-body
woobe project lifecycle operation 550e8400-e29b-41d4-a716-446655440000
```

The operation command is read-only and returns the original audited receipt.
After a timeout, an absent observation does not authorize another write. Retry
only the identical original operation when its outcome permits recovery;
never generate a replacement UUID for an uncertain submission.

`production_actors` optionally narrows who may plan/apply Production deployment.
Entries are `user:UUID` or `control:UUID`, using the stable credential identity,
not a CLI key secret or a rotated key row ID. An empty list preserves ordinary
Production grants. The listed actor still needs the target/environment-scoped
Production permission. Use the actor identity in a prior authoritative operation
receipt; do not guess it from a masked key.

A policy change increments its generation and invalidates deployment plans
captured under the earlier policy. Read fresh selection/policy state and create
a new plan for a confirmed stale-plan rejection. Do not replay an uncertain
apply under a new operation. The server locks policy through final deployment
commit and retains an immutable policy receipt and outbox audit.

These commands use the selected connection, authentication and Project without
requiring `.woobe-config`. They are available only when the backend advertises
the reviewed API; incompatible backends fail before a policy write. JSON and
YAML bodies share the same server validation. Git provenance, offline receipt
signatures and Web editing are separate lifecycle features.

Agent tests by Staging/Production environment resolve the authoritative ASaC
selection and accept its exact immutable Release. Preparation checks the selected
identity while locking the environment observation; stale selected UUIDs are
rejected. Legacy Staging-kind snapshots remain compatible where ASaC has no
selection. This does not relabel, copy or publish a Release.

## Unified delivery

See [Deployment](DEPLOYMENT.md) for exact Release/Staging/local delivery, private intent recovery and explicit rollback. See [CI deployment](CI_DEPLOYMENT.md) for deploy-only authority and encrypted checkpoints. Existing commands retain their semantics.
