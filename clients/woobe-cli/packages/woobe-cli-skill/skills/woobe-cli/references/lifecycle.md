# Tests and native lifecycle

Lifecycle operations use saved server snapshots; they do not upload local YAML.
Push and inspect Draft changes first. For a specifically authorized Agent flow:

```sh
woobe agent '@support' stage --yes
woobe agent '@support' test --file ./support-test.yaml --yes
woobe agent '@support' publish --notes "Reviewed support changes" --yes
woobe agent '@support' release list --output compact
woobe agent '@support' activate --version ACTUAL_RELEASE_VERSION --notes "Approved deployment" --yes
```

Stage copies current Draft to Staging. The test executes saved Staging by default,
records a real Run/result and exits 6 on failure. The bundled
[testcase](../assets/agent-test.yaml) shows `message`, optional `expected_output`
and `external_context`; adapt it to the requested acceptance criteria. For Draft
tests use `--env draft`; a Release test needs `--env release --version VERSION`.
Passing local YAML validation is not a successful execution test.

Agent publish creates an immutable Release from Staging; activate selects its
actual returned version. Do not fabricate a version or assume publish activated
the Agent. Rollback requires an explicit older Release, audit reason and `--yes`.
Archive/delete follows native dependency checks and requires authorization;
local `resources unregister` does not delete the remote Agent.

For Networks, `stage` freezes constituent snapshots. **Network publish also
activates its Release in Production**, following Woobe's native behavior. Obtain
authorization for that Production effect before adding `--yes`; do not present
it as a harmless Release-only action. Network constituent Agents are not
automatically activated as standalone Production Agents. Network activate/
rollback selects an explicit immutable version with `--notes` and `--yes`.

Native UUIDs work without `.woobe-config`; aliases/paths need connection-scoped
bindings. Denied operations do not become allowed by supplying `--yes`.

## Exact isolated revision preparation (CLI 0.24+)

For an isolated historical Draft, use `stage --revision REVISION_ID --yes` after
`draft push`, `revision create --message ...` and `draft checkpoint REVISION_ID`.
Inspect first with `--dry-run`. This uses the verified retained executable object
and exact remote Draft generation; later YAML edits are not included. Provider
bindings must already exist. Network and Agent syntax is identical.

Acceptance returns `preparing` and a Candidate UUID. Read
`woobe agent '@support' candidate CANDIDATE_UUID` (or Network) to inspect progress;
use the preparation operation ID with `woobe package status OPERATION_UUID` for
errors/dependencies. Ready means the detached closure is frozen, not that tests
passed or publication occurred. Do not feed it into legacy publish/activate.

If acceptance is uncertain, use `draft reconcile` before another Stage; preserve
its original ID. Stage does not save current YAML, select native Staging, publish
or activate Production. Without `--revision`, Stage retains the legacy behavior
documented above. Never silently fall back when Candidate support is absent.

```sh
woobe agent '@support' stage --revision rv_00000000-0000-0000-0000-000000000000 --dry-run
woobe network '@customer-support' stage --revision rv_00000000-0000-0000-0000-000000000000 --dry-run
```

Replace the revision placeholders with actual registered checkpoints before use.

## Exact Candidate evaluation

After an isolated `stage --revision`, inspect the Candidate until its state is
`ready`. Evaluate its UUID with a versioned YAML suite; current local YAML and
native environment selections cannot replace this frozen snapshot.

```yaml
schema_version: '1.0'
suite_id: support-smoke
suite_version: '1'
dataset_version: '1'
policy_version: all-cases-pass@1
cases:
  - id: greeting
    message: Hello
    # Optional: expected_output is compared to actual structured output,
    # or {answer: ...} for unstructured text. Omit it for execution/schema checks.
```

```sh
woobe agent '@support' test --candidate CANDIDATE_UUID --file suite.yaml --yes
woobe network '@helpdesk' test --candidate CANDIDATE_UUID --file suite.yaml --yes
woobe agent '@support' evaluation EVALUATION_UUID
woobe network '@helpdesk' evaluation EVALUATION_UUID reconcile --yes
```

The suite accepts 1–16 uniquely named cases. Suite, dataset and policy versions
are declared identities; the backend separately verifies content digests. Every
case gets its original native Run identity before execution. Qualification uses
actual terminal Run evidence, exact snapshot identity, output validation and
current binding fingerprints. Missing evidence stays incomplete. Failed cases
exit with code 6; `accepted` and `running` do not mean passed.

The immutable acceptance receipt identifies the evaluation. Inspect its ledger
for the current result. If acceptance is uncertain, use `draft reconcile` before
another write: it recovers the original receipt and never executes a case again.
The evaluation's own `reconcile` reads original Run evidence without provider
calls. Neither command publishes nor changes Production. Do not combine
`test --candidate` with `--env` or `--version`. Native Agent `test --env` remains
available; Network testing requires an exact Candidate. Inspection by native UUID
works without `.woobe-config`; accepting an evaluation uses private project state
to preserve its write identity. Exact Candidate evaluation requires CLI 0.25+
and a backend advertising `asac.candidate_evaluation`.

## Publish an exact evaluated Agent Candidate

```sh
woobe agent '@support' publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes 'Validated support update' --yes
woobe agent AGENT_UUID publication PUBLICATION_UUID
woobe agent '@support' history verify
```

This explicit flow requires CLI 0.26+ and a backend advertising Agent in
`asac.candidate_publication_kinds`. It requires a ready Candidate and a passed
Evaluation for the same retained revision, runtime and bindings. The server
rechecks those bindings and publishes the frozen Candidate, even if current
Staging subsequently changed. It never pushes local YAML or activates Production.
Native Release reuse still produces a separate publication provenance receipt.

Acceptance requires the registered development resource and its private state;
inspection by native UUID does not require `.woobe-config`. The CLI persists the
original operation before POST and mirrors its immutable receipt after acceptance.
An unknown remote outcome blocks another write. A local documentary failure after
remote commit exits with code 10 and retains the pending operation. In both cases,
use `woobe agent '@support' draft reconcile`: it reads the original operation and
retries the local mirror, without another publication request.

`history verify` checks receipt integrity and destination identity. Its
`publication_authenticity: integrity_checked_connection_unverified` distinguishes
an authenticated fetch observation from a signed offline attestation. Git claims
remain declared; this flow does not claim verified pipeline provenance.
Legacy publication without `--candidate` retains its native behavior; in
particular, legacy Network publication activates Production. Exact Network publication uses the explicit Candidate flow below.


## Publish and recover an exact Network Candidate

```sh
woobe network '@support-network' publish --candidate CANDIDATE_UUID --evaluation EVALUATION_UUID --notes 'Validated Network update' --yes
woobe network NETWORK_UUID publication PUBLICATION_UUID
woobe network NETWORK_UUID publication PUBLICATION_UUID reconcile --yes
woobe network NETWORK_UUID publication PUBLICATION_UUID cancel --notes 'Discard unfinished preparation' --yes
woobe network '@support-network' draft reconcile
woobe network '@support-network' history verify
```

Use CLI 0.27+ with a backend advertising Network Candidate publication. Prepare
and evaluate a new Candidate with `network-execution-runtime@2`; historical
Candidates retain their original runtime scope. Publication copies or reuses
immutable constituent Agent Releases through their owning module and creates the
Network Release from that exact tested composition. Production, current native
Draft/Staging and standalone Agent environment selections remain unchanged.

The server accepts the original publication before constituent copying. A failure
can leave `state: preparing` with prepared/required counts. The CLI exits 9 and
retains its pending operation, blocking a second publish. Inspect the returned
Publication UUID, then explicitly resume with `publication ... reconcile --yes`.
The server rechecks current permissions, original Evaluation and binding versions;
resume reuses original child-operation receipts rather than copying twice.

Alternatively, cancel an unfinished preparation with a reason. Cancellation seals
it without publishing the Network; already copied immutable Agent Releases remain
retained. Cancellation cannot undo a completed publication. These native UUID
recovery operations do not require `.woobe-config`.

After either terminal outcome, use `draft reconcile` for the original local
operation. It only reads original acceptance/current phase, mirrors the publication
or cancellation receipt, and clears pending state after the mirror succeeds.
It never repeats publication, constituent copying or activation. Documentary
failure exits 10 and remains recoverable; `history verify` checks both receipt
collections. Offline verification proves content integrity, not server authenticity.

## Bounded workflow reservations

Use CLI 0.28+ with a backend advertising `asac.operation_leases`. Reserve only
the short authoring workflow that needs exclusivity; frozen Candidate evaluation
does not need a long global lock. Agent and Network share the protocol.

```sh
woobe agent '@support' lease acquire --scope draft --ttl 60
woobe agent '@support' draft push
woobe agent '@support' lease renew --scope draft --ttl 120
woobe agent '@support' lease show --scope draft
woobe agent '@support' lease release --scope draft
woobe agent '@support' lease reconcile
```

`--scope resource` (default) reserves authoring across Draft lines. `--scope draft`
uses the selected isolated Draft; `--draft DRAFT_UUID` selects an explicit one.
A native UUID with draft scope and no Draft ID deliberately reserves the legacy
native default Draft, whose old write schema cannot carry workflow proofs.
Staging/Production scopes reserve selection workflows; lease storage alone does
not make a legacy activation fenced. Reads, tracing and Runs remain available.

Registered aliases store distinct workflow/operation identities before submitting
and keep accepted proofs privately under `.state`. Isolated Draft open/save/
checkpoint attach the relevant exact proofs. Do not commit or copy this state.
The same CLI Key does not make another workflow the owner. Server database time
and bounded maximum duration decide expiry; expired/superseded proofs remain
attached so the server can fence a stale writer instead of silently treating it
as unreserved. Explicit owned release permits subsequent unreserved authoring.

A lost response or failed private receipt leaves the original operation pending.
`lease reconcile` or `draft reconcile` reads that original acceptance, verifies
its scope, destination and workflow, saves the proof, then clears pending state.
It never submits acquire/renew/release again. A historical accepted lease receipt
does not promise the reservation is still valid. `show` observes current state
without adopting another workflow or refreshing local ownership.

Native UUID operations need no `.woobe-config`. Supply stable `--operation UUID`,
`--workflow UUID` for acquire, and the exact `--lease UUID --fencing-token NUMBER`
plus workflow for renew/release. Retain the original operation for `lease reconcile
--operation UUID`; this is a read and never implicitly repeats a mutation.
Administrative `break` needs exact lease/fence, `--yes`, a meaningful `--reason`
and server `project:access:write`. It cannot break a newer replacement lease.
Fencing counters are positive integers, not authentication tokens. CAS and current
authority remain mandatory; a reservation is not evidence of a correct base.

## Exact Release deployment plans

Publication and selection are separate. With CLI 0.29+ and a backend advertising
`asac.fenced_deployment`, plan an exact evaluated published Release and apply that
plan with an owned environment lease. Agent and Network use the same commands.

```sh
woobe agent '@support' current --env production
woobe agent '@support' deployment plan --release RELEASE_UUID --expected-generation 4 --notes 'Deploy the qualified revision'
woobe agent '@support' lease acquire --scope production
woobe agent '@support' deployment apply PLAN_UUID --yes
woobe agent '@support' deployment show DEPLOYMENT_UUID
woobe agent '@support' lease release --scope production
```

Replace `4` with the observed environment generation. Add `--env staging` to
plan/apply/show and reserve `--scope staging` to select Staging. Add
`--action rollback` when planning an exact prior qualified Release; rollback
still requires current generation, bindings, authorization and a new short lease.
`--publication PUBLICATION_UUID` selects exact retained provenance; when omitted,
the server selects matching evidence once and freezes its identity in the plan.
No Release is rebuilt, no Draft is overwritten, and planning does not activate.

Plans have a server database deadline. Changed selections (including A → B → A),
bindings, policy, runtime content or authority invalidate application. The server
updates the pointer, immutable deployment receipt and outbox atomically, checks
lease expiry again at commit and fences old workflows. A resource-authoring lease
is independent and cannot authorize an environment selection. Once an environment
uses ASaC selection authority, legacy selection writes are rejected; use a new
exact plan instead.

Registered aliases retain the operation before submission and mirror its
immutable receipt before clearing pending state. After a lost response, use:

```sh
woobe agent '@support' deployment reconcile
```

This reads original acceptance only; never repeat apply to guess whether it
committed. `draft reconcile` also recovers deployment operations. Exit 9 means
acceptance is unproven; exit 10 means the documentary mirror still needs repair.
Local mirrors establish integrity and an authenticated connection observation,
not offline server authenticity.

Native UUID commands work without `.woobe-config`. Writes require a stable
`--operation UUID`; apply additionally requires the original `--lease UUID
--workflow UUID --fencing-token NUMBER`. Save the operation UUID for
`deployment reconcile --operation UUID`. `plan-show PLAN_UUID` and
`show DEPLOYMENT_UUID` are reads and never select an environment.

A registered lease/deployment target can resolve its native identity from the
durable lock after private state is lost. The origin must match the selected API,
workspace and project; this does not restore author bindings, credentials or a
synchronized base. Environment leases still require a new owned workflow.


## Project lifecycle authority

`woobe project lifecycle show` reads managed mode and policy generation without
local development config. Policy changes require `project:access:write` and
YAML/JSON fields `operation_id`, `expected_generation`, `managed`,
`production_actors`, `reason`. `woobe project lifecycle update --file policy.yaml`
requires an advertised backend. Read the exact original change with
`woobe project lifecycle operation OPERATION_UUID` after uncertain acceptance;
never issue a replacement operation UUID while an earlier write is uncertain.

An empty actor list preserves ordinary Production grants. Stable `user:UUID`
or `control:credential-UUID` entries narrow them without granting authority.
Managed Projects reject legacy promotion; use exact Candidate evaluation,
publication and leased deployment instead. Policy changes invalidate older
plans. Existing admitted Runs remain pinned. Do not automatically disable a
managed policy to make a promotion work.


```sh
woobe project lifecycle show
woobe project lifecycle update --file ./lifecycle-policy.yaml --validate-body
woobe project lifecycle operation OPERATION_UUID
```

The update example requires a reviewed policy file with an explicit operation
UUID/current generation and administrative policy authority; it is not a
ready-to-apply template. Preserve the original operation after uncertain writes.

For server-signed export and offline verification with a separately pinned root,
read [signatures](signatures.md). Unsigned history integrity checks do not
establish offline server authority.

On compatible backends, `agent test --env staging` resolves the authoritative
ASaC selection: an immutable Release selected in Staging stays a Release, and
its exact UUID is tested without copying it to a Staging-kind snapshot. A changed
selection rejects the stale testcase; legacy native Staging snapshots still work.
Use `current --env staging` to inspect authority/generation.

For unified delivery and original intent recovery, read [deployment](deployment.md). Native UUID deploy works without the development registry; local delivery requires accepted source and bindings.

## Native Prompt/Contract snapshots and saved tests

Choose exact `prompt_version_id` / `contract_version_id` in a native Draft save;
omit contradictory embedded text/schema. The backend materializes their selected
content and freezes the Contract material. Saving Draft adopts deliberate changes;
existing captures and exports keep their original material. Incomplete historical
immutable snapshots need a new complete capture, not rewritten hashes.

Tests validate the effective schema even without expected_output. Missing required
schema records CONTRACT_MISSING without a provider call; invalid JSON/fields fail
with exit 6. Inspect validation_errors and actual_output.output_valid; provider
completion alone is insufficient. Strict runtime rejection can retain private invalid-output evidence for the
authorized test, but cannot turn a failed test into passed. Quote --fields in PowerShell.
For timeout use the original test UUID/read command in [recovery](recovery.md).
