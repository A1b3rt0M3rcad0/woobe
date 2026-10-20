# Unified Agent and Network deployment

`deploy` orchestrates the existing ASaC owner contracts. It does not deploy the
Woobe server, transfer resources between instances or bypass Project policy.
For an installed package, first confirm `woobe agent AGENT_UUID deploy --help`;
a draft PR artifact is not a published npm release. Agent and Network use the
same interface:

```sh
woobe agent AGENT_UUID deploy --from release --release RELEASE_UUID --notes 'Approved delivery' --yes
woobe network NETWORK_UUID deploy --from staging --notes 'Promote verified Staging' --yes
woobe agent '@support' deploy --from local --suite tests/evaluation.yaml --notes 'Deliver author changes' --yes
woobe network '@support' deploy --from local --suite tests/evaluation.yaml --via-staging --smoke tests/staging-smoke.yaml --notes 'Deliver through Staging' --yes
```

The default destination is Production; `--env staging` selects Staging. UUIDs
need only connection/Project/CLI Key, with no `.woobe-config`. Registered `@alias`
and paths resolve exactly in the selected local registry. Display-name inference
and implicit resource creation are deliberately excluded from deployment.

## Sources and qualification

| Source | Required evidence | What changes |
| --- | --- | --- |
| `release` | Exact `--release UUID`; optional exact `--publication UUID` | Server qualifies that published, evaluated immutable Release, then fences its selection |
| `staging` | Current Staging selects an immutable ASaC Release | Captures its UUID/generation, refuses drift before apply, promotes that same Release; never republishes |
| `local` | Accepted registered binding/source export, retained source, valid closure and explicit Candidate suite | Seals local Revision; opens an isolated intent Draft; pushes/checkpoints; prepares exact Candidate; evaluates; publishes; deploys exact Publication |

Local delivery does not refresh missing or stale bindings, pull over edits,
import duplicates or select the latest Candidate. Use explicit `bindings recover`,
Provider binding and source recovery first. Its isolated Draft starts from the
retained accepted export, rather than recapturing a different native Draft.
Author/suite changes before delivery finishes conflict with the frozen intent;
restore the exact source or create a new intentional delivery. Once Publication
is retained, resume uses that Release and does not republish changed files.
Network preparations may remain accepted but unfinished. Resume observes and
reconciles the original preparation, preserving copied constituent Releases.

Before allocating a local Revision, the CLI requires the backend capability
`asac.draft_source_preflight`. The read-only owner check verifies the retained
export's actor, expiry, target, logical UID and native Draft generation. It then
checks that each local parent is an exact remotely accepted Revision. Upgrade the
backend before using local delivery with this check; release/staging delivery
continues to use its existing contracts. Opening/checkpointing still repeats the
owner checks under concurrency controls: preflight cannot reserve future state.

| Blocker | Recovery |
| --- | --- |
| `ASAC_ORIGIN_MISMATCH` | Preserve edits/history; explicitly pull the intended native target. A clone/import binding can still retain its source's export. |
| `ASAC_SOURCE_CHANGED` | Inspect changes since capture, including managed push. Preserve author changes and explicitly refresh/reconcile the intended source before a new intent. |
| `ASAC_HISTORY_INCOMPLETE` | Reconcile prior intents, then register exact missing ancestors in parents-first order in isolated Drafts matching those artifacts. `history verify` proves local integrity, not server acceptance. |

These failures do not allocate a new local Revision or open a remote Draft during
preflight. Never delete/rewrite parents to bypass a conflict. A revision committed
locally before its intent journal save failed is reused only by that exact intent
and artifact. Resume of a submitted Draft opening observes its original operation
instead of requiring a new export ticket or repeating the write.

Candidate suite example ([file](examples/deployment/evaluation.yaml)):

```yaml
schema_version: '1.0'
suite_id: delivery
suite_version: '1'
dataset_version: '1'
cases:
  - id: greeting
    message: Hello
```

Use the backend's supported evaluation assertions for product-specific gates.
A suite must contain 1–16 cases with unique IDs and nonblank messages. The CLI
validates fields and bounds before creating an isolated Draft/Revision, preserves
exact YAML/JSON numbers, and leaves final qualification to the backend. Production
is never reached after failure.

`--via-staging` applies only to local delivery to Production. It deploys the same
Release to Staging, executes a fresh Session using a **separate Runtime Key** and
requires the intended target/Project/environment/snapshot plus exact expected
output. Candidate suites and Runtime smokes are different documents:

```yaml
schema_version: '1.0'
target_alias: support
request:
  input: Hello
expected_output: Hello from support
```

The example assertion is a placeholder; replace it with your actual expected
response. A failed or uncertain smoke preserves Staging and blocks Production.
An uncertain Run is never automatically repeated. Inspect its original Run
before starting another authorized intent. External dependencies remain live
versioned references, not deterministic external responses.

## Intent, recovery and concurrency

Each delivery gets an `intent_id`. Supply `--intent UUID` for a stable CI intent.
Separate deterministic operation IDs are scoped to API, Workspace, Project,
kind, native target, intent and step. A private locked journal retains payloads
before sending writes, followed by validated receipts. Default location is the
private CLI configuration directory's `deploy-intents/`; `--checkpoint PATH`
selects an explicit private destination. POSIX parent must be 0700/file 0600;
Windows uses a private DACL. Do not commit or publish this operational state.

```sh
woobe agent AGENT_UUID deploy status --intent INTENT_UUID
woobe agent AGENT_UUID deploy resume --intent INTENT_UUID --yes
woobe agent AGENT_UUID deploy inspect --env production
```

Status reports documentary journal evidence, not a fresh claim about current.
Resume needs the same API, Project, principal, target and original private journal.
The backend must advertise `asac.operation_environment_reads`: deployment/lease
recovery reads carry their exact environment and the owner verifies the retained
receipt scope. A Production-only deployer never needs Draft access for recovery.
It observes submitted operations; 404 or `not_observed` never permits re-POST.
Missing state blocks resume. A completed resume is read-only and checks current
before claiming it still matches. A changed destination is an explicit conflict.

Deployment acquires its environment lease only after qualification, close to
apply. Owner CAS, database-clock leases, fencing, policy/binding fingerprints,
immutable receipt and transactional outbox remain authoritative. Expired plans,
leases or changed policy require inspection and a new intention after reconciling
submitted apply; the CLI never breaks someone else's lease or rolls back silently.
Response loss during apply is recovered from the original operation/deployment.
Receipt/current disagreement reports a committed but unconfirmed outcome, not
success. Lease cleanup failure retains the original cleanup operation for resume.

An already selected, qualified Release is reported `already_selected` with the
same generation and no new apply. Rollback is an explicit new audited selection:

```sh
woobe network NETWORK_UUID deploy --from release --release PREVIOUS_RELEASE_UUID --action rollback --notes 'Restore qualified version' --yes
```

Rollback does not infer an older version or weaken qualification. An expired
key, insufficient grant or disallowed Production actor remains denied.

## Preflight and output

`--plan-only` and global `--dry-run` perform read-only source/capability/current
checks. They create no server plan, Revision, Candidate, provider Run, lease or
selection. Output says `executed: false` and `server_qualification: not_evaluated`.
A successful preflight is not an authorization or qualification guarantee.

Text/compact output preserves full recovery IDs and relevant states. JSON adds
per-step operation states, original source and local evidence. Successful apply
reports Release/Publication/Deployment IDs, previous Release, generations,
actor, `write_outcome` and observed-current agreement. Git verification is
`not_evaluated`: orchestration does not manufacture Git attestation or signatures.
Use [existing provenance](GIT_PROVENANCE.md) and [signed receipts](SIGNED_RECEIPTS.md)
when the Project requires those independent proofs.

See [CI deployment](CI_DEPLOYMENT.md) for protected deploy-only identities and
securely retained CI recovery. Existing `deployment`, `lease`, `activate`,
`rollback`, `stage`, `test` and `publish` keep their previous semantics.
