# Exact delivery and CI recovery

Use this flow only when the user authorizes the selected environment's activation.
Check `woobe agent UUID deploy --help` for availability. Older CLI versions do not
have this orchestrator; update to a release containing it before using examples.

```sh
woobe agent AGENT_UUID deploy --from release --release RELEASE_UUID --notes 'Approved delivery' --yes
woobe network NETWORK_UUID deploy --from staging --notes 'Promote verified Staging' --yes
woobe agent '@support' deploy --from local --suite tests/evaluation.yaml --notes 'Deliver author changes' --yes
woobe agent AGENT_UUID deploy status --intent INTENT_UUID
woobe agent AGENT_UUID deploy resume --intent INTENT_UUID --yes
woobe agent AGENT_UUID deploy inspect --env production
```

Release mode uses a qualified immutable UUID; native UUIDs need no project config.
Staging mode captures the exact ASaC selection and refuses drift, with no republish.
Local mode requires accepted source/bindings and a versioned Candidate suite. It
seals an immutable Revision, opens an isolated intent Draft, prepares/evaluates an
exact Candidate, publishes it and fences activation. Never import duplicates,
auto-recover missing bindings, replace newer remote work or bypass failed tests.
Read [development](development.md) for explicit source/Provider recovery.

`--via-staging --smoke FILE` is local-only and requires a separate Runtime Key.
Smoke YAML has schema_version '1.0', target_alias, request {input: ...}, and exact
expected_output. It runs a fresh Session and proves target/environment/Release.
Failure or an unknown Run blocks Production; never repeat an uncertain Runtime
execution. Candidate evaluation suite and Runtime smoke are different documents.

Preserve the private intent journal and original operation IDs. Resume observes
submitted writes before advancing; 404/not_observed is not permission to retry.
CI must restore its encrypted/private checkpoint, otherwise block rerun. Never
publish `.state`, credentials, raw checkpoints or Provider bindings. Once published,
resume keeps that Release instead of reading new author changes. Status is historical
documentary evidence; inspect reads current. Successful completed resume rechecks
current. Report committed-but-unconfirmed and cleanup-pending honestly.

Deploy defaults to production; --env staging is explicit. --plan-only/--dry-run are
read-only preflight, not server qualification. Require --notes and authorization
before --yes. Rollback uses --from release --release PREVIOUS_RELEASE_UUID
--action rollback, with a new audit intention and the same qualification gates.
Do not infer latest/previous or roll back automatically. Protected CI uses a scoped
Production Control Key and managed policy's stable production actor allowlist;
Runtime Keys never authorize administration. Git verification remains separate.

Scoped deployment recovery requires backend capability `asac.operation_environment_reads`. The CLI reads each original deployment/lease operation with its exact environment; it never asks a deploy-only key for Draft access.

Candidate suites use unique case IDs and nonblank messages; malformed/unknown fields are rejected before authoring writes, and numeric assertions retain exact YAML/JSON precision. Final evaluation remains backend-owned.

Local delivery additionally requires `asac.draft_source_preflight`. Upgrade the
backend first. Before sealing a Revision, the CLI checks capture target/actor/
expiry/UID/Draft generation and exact server acceptance of local parents. A
successful preflight does not reserve state; owners recheck on mutation.
For `ASAC_ORIGIN_MISMATCH` or `ASAC_SOURCE_CHANGED`, preserve local edits/history
and explicitly recover the intended target's capture. Managed push can make an
older Draft capture stale. For `ASAC_HISTORY_INCOMPLETE`, inspect the listed
parents-first IDs, reconcile original intents, and checkpoint each exact ancestor
in a matching isolated Draft before a new deploy. Do not delete parents, invent
remote acceptance, or confuse local history verification with server acceptance.
