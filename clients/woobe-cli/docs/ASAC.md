# ASaC tracking and immutable local revisions

Managed pull bootstraps `agent.lock.yaml` or `network.lock.yaml` in the registered
resource directory. Flat descriptor paths use a sibling `<stem>.asac/` directory
to avoid collisions. Tracking records resource UID, origin destination and native
snapshot, tracking environment, working revision and portable requirements. It
excludes credentials, export tickets, leases and private CAS observations. Repeated
pulls/checkpoints preserve origin. Unproven origin is `unknown_origin`.

```sh
woobe agent '@support' revision create --message 'Correct citation instructions'
woobe agent '@support' history
woobe agent '@support' heads
woobe agent '@support' revision show REVISION_ID
woobe agent '@support' revision diff REV_A REV_B
woobe agent '@support' history verify
```

Networks use the same commands. Checkpoints have random opaque IDs, explicit
parents and a closed package captured through the existing compiler.
`--parent REVISION_ID` can name multiple existing parents for already resolved
content; it does not automatically merge anything. Same content with different
lineage remains a different revision. Sealed records are append-only. Objects
live at `.woobe/objects/sha256/<artifact-digest>.tar.gz` and use normal package
inventory/locked-archive validation.

`definition_digest` reflects dependencies and support bytes, independently of
aliases and destination credential IDs. `record_digest` includes lineage and
identity but excludes itself. Shared Go/Python fixtures define the type-preserving
`woobe-asac@1.0` canonicalization. Existing package artifact digests are unchanged.
Missing parents, missing objects and runtime executability are separate facts.
Local history does not promise remote freshness. A clone can inspect/checkpoint
using tracking requirements without copying `.state`; remote writes still require
validated bindings and authority.

## Recover native bindings after cloning

```sh
woobe agent '@support' bindings recover --dry-run
woobe agent '@support' bindings recover
woobe network '@service' bindings recover
woobe resources bind provider '@primary' CREDENTIAL_UUID
```

Recovery reads the destination registry and restores private native identities
and their **accepted** generations for the complete registered closure. It
requires prior successful synchronization in that registry. A native UUID can
resolve through matching durable origin without `.state`; ambiguous origins
require an alias. No server writes, YAML edits, head changes or Production changes
occur. Providers still require explicit verified binding; credentials are not
restored.

The response says `author_base: not_recovered`. Identity evidence cannot prove
that today's local YAML was accepted. Native edits remain stale accepted bases
and are rejected by subsequent write CAS; recovery never refreshes the accepted
generation to hide that conflict. Existing contradictory bindings, missing
dependencies, unsealed operations and uncertain local writes block recovery
without partially changing state. Reconcile pending writes first.

Frozen Network constituents retain an exact `snapshot_id` in `.woobe-config`.
Legacy canonical `snapshots/AGENT_UUID/SNAPSHOT_UUID` paths remain recognized.
Reuse requires the server's retained owner snapshot proof and unchanged full
definition/bindings. It never selects the latest Agent version. Unavailable
legacy evidence is rejected rather than treated as synchronized content.

## Observe the remote

```sh
woobe agent '@support' status --remote
woobe agent AGENT_UUID current --env production
woobe agent '@support' history fetch
```

`current` is always remote and accepts UUID without a local registry. Status stays
local unless `--remote` is supplied, and distinguishes `local_modified`,
`draft_changed` and `tracked_ref_changed`. Observing changed Production does not
rewrite origin. Legacy selection reports `generation_status: legacy_unavailable`;
a release ID is not an environment CAS generation.

Fetch traverses stable watermarks for publication/deployment streams and stores
destination-scoped immutable receipts without editing author files or Production.
Dry-run validates pages without writing receipts. Hashes verify integrity;
authenticated observations are not signed offline attestations or verified Git
provenance.

These commands do not change native lifecycle effects: Agent publish creates a
Release; legacy Network publish also activates Production. Checkpoints do not
grant authority or provide deployment fencing. Isolated Draft storage is explicit
and described below.
Check actual command/server compatibility before using a newer contract.

## Isolated remote Drafts

```sh
woobe agent '@support' draft list
woobe agent '@support' draft open hotfix --from production
woobe agent '@support' draft select hotfix
woobe agent '@support' draft show
woobe agent '@support' draft push
woobe agent '@support' revision create --message 'Correct citation instructions'
woobe agent '@support' draft checkpoint REVISION_ID
woobe agent '@support' draft reconcile
```

Networks use the same commands. Opening captures an authorized exact source
(`draft`, `staging`, `production`, or `release --version VERSION`) and selects its
remote Draft for subsequent `draft push`. It preserves local author files and
the existing native default Draft. It is not a local checkout: review/diff local
YAML against the chosen source before saving it. Ordinary `push` remains the
existing native Draft synchronization command; the explicit `draft push` saves
an isolated closed object. No publication or activation occurs.

The server must advertise compatible isolated Draft support and the portable
definition digest scope. An unsupported server is refused before opening/saving;
there is no fallback that writes the default Draft instead. Save uses the last
observed Draft generation. `draft show` refreshes it; review remote changes before
retrying a conflict. Checkpoint registration requires an existing local revision
whose exact object matches the saved isolated Draft and current YAML. Changing
YAML after sealing is rejected. Providers outside its closure are excluded.

Draft selection and pending operation payloads live in destination-scoped private
`.state`. An operation ID is persisted before its request. A definite rejection
clears the pending write; an uncertain outcome blocks additional writes until
`draft reconcile` observes the original receipt. Reconcile never repeats POST/PUT.
`not_observed` is incomplete and does not authorize another mutation. Read-only
listing/inspection remains available. A fresh clone can open a Draft through its
matching durable origin; the server verifies authority and logical/native binding.
Use `draft select NAME_OR_UUID` to recover an existing isolated Draft selection
without opening a duplicate. It verifies the logical UID and native root and
refreshes that Draft's observed generation. It writes only private selection
state: author files and server resources remain unchanged. `--dry-run` performs
these reads without saving the selection. An unresolved original write blocks
selection until reconciled. Selection does not recover native push bindings or
Provider credentials; keep/rebind those separately. A known origin cannot use
`create` to duplicate its root merely because private bindings are absent.

Isolated saves currently validate closed package schema/inventory. Output reports
`semantic_validation: stage_required`; runtime candidate qualification and fenced
deployment are separate negotiated contracts. The storage commands alone do not
make an isolated Draft executable or eligible for legacy promotion.

## Restore local author source

```sh
woobe agent '@support' checkout --revision REVISION_ID
woobe network '@customer-support' checkout --revision REVISION_ID
```

New checkpoints retain exact author descriptors (including YAML comments) and
support bytes in bounded immutable `.woobe/objects/author/<digest>.json` objects.
The revision links this source using `author_artifact_digest`; this hash is
separate from the verified portable executable definition. Checkout compiles the
retained source in an isolated scratch registry and checks its definition and
component identities before writing. It preserves current aliases, paths, origin
and private destination bindings. The working revision changes locally; remote
Drafts, Releases and Production do not change.

Checkout requires working files to match their current source checkpoint. It
rejects edits, changed shared dependency files, tampered source objects and
unregistered target files. `--yes` cannot bypass those protections. Checkpoint
edits explicitly before restoring another revision. Older revisions without
retained author source remain readable but cannot use this local restore.

Remote checkpointing negotiates `author_source_retention` and uploads the exact author object before registering its immutable revision. Upload tickets are actor scoped and expire; retained source remains readable through the authorized Agent/Network revision with another permitted CLI Key. Older backends retain declarations only (`declared_not_retained`). The server labels verified canonical custody separately from compiler attestation.

## Reconcile sealed local branches

```sh
woobe agent '@support' rebase --onto REVISION_ID
woobe network '@customer-support' rebase --onto REVISION_ID --message 'Reconcile network changes'
woobe agent '@support' revision merge REV_A REV_B --message 'Resolved combined content'
```

Rebase computes a three-way semantic merge of the current checkpoint and the
selected revision against their known common ancestor. It merges independent
object fields, treats arrays and support files as atomic, validates the complete
result in scratch space, and seals a new revision whose parent is `--onto`.
Original revisions and origin remain unchanged. Surviving YAML field comments
are carried forward when fields are recomposed; a comment-only incoming change
is also retained. Competing comment edits report `/author_comments`; deleting a
component concurrently with an author-source edit reports `/author_source`.
Deleted fields have no place to retain their comments. JSON descriptors remain JSON. Private destination bindings
are unchanged. The result is local, not a remote push or deployment.

Rebase requires clean checkpointed files. Conflicts report component/field paths
with `ASAC_REBASE_CONFLICT` (exit 6) and do not change files or revision history.
Incomplete ancestry is not guessed; obtain missing history first. Multiple common
ancestors require an explicit `--base REVISION_ID`, which must be an ancestor of
both branches. Review `revision diff` before writing; `--yes` does not discard edits.

`revision merge REV_A REV_B` seals the **currently resolved author content** with
both immutable parents. It does not silently choose a winner or merge YAML for
you. Resolve conflicts and validate the resulting files before this checkpoint.
Neither command publishes, stages, activates nor rewrites a shared revision.

Source verification uses the compiler recipe recorded in the author object.
Older objects without a recipe use the original Provider-to-Model lowering;
new objects use `woobe-development-compiler@2.0`, keeping Model endpoint overrides
separate from Provider defaults. Checkout validates the historical object using
its own recipe; a new checkpoint uses the current one. Unknown recipes are
rejected rather than silently reinterpreted.


### Fetch isolated revision metadata

Use `woobe agent @support history fetch --revisions` (or the same Network
command) to append the authorized server revision catalog. It checks immutable
record digests, logical identity, page completeness and a stable watermark.
The default `history fetch` continues to retrieve native release/deployment
receipts. Neither mode changes author YAML, the working head or Production.

Revision metadata and source materialization are separate: this fetch reports
`objects_available: not_downloaded`. A remote source digest is a declaration,
not a retained author object or a server attestation. Local checkout still
requires verified executable and exact author objects. `--dry-run` validates
the catalog without storing metadata. A failed traversal can retain earlier
immutable pages, but never reports that traversal as complete.


### Hydrate executable and exact author objects

```sh
woobe agent @support history fetch --revisions
woobe agent @support revision hydrate rv_00000000-0000-0000-0000-000000000000
```

Replace the revision placeholder with a verified retained ID. Agent and Network
use the same operation. It negotiates backend hydration support, reauthorizes
the retained resource and verifies the receipt, transport SHA-256, inventory,
artifact digest and executable definition before storing an immutable object.
`--dry-run` downloads and verifies without storing. Source YAML, native bindings,
working head and Production are preserved. If source custody is available, hydration verifies its canonical author hash, exact YAML/support inventory and recorded compiler recipe against the executable definition and every component identity before storing source. It reports `author_object: verified_source_and_compilation`; a separate guarded checkout restores working files. An old record without retained source still permits executable hydration and reports source unavailable. Credentials and native bindings remain separate; hydration does not qualify runtime execution.

Guarded checkout verifies both the current clean source anchor and the target revision. If author objects were removed or absent in a clone, hydrate both revision IDs first. This recovery never bypasses protection of local edits.

## Prepare an exact immutable Candidate

```sh
woobe agent '@support' draft select hotfix
woobe agent '@support' draft push
woobe agent '@support' revision create --message 'Reviewed hotfix'
woobe agent '@support' draft checkpoint REVISION_ID
woobe agent '@support' stage --revision REVISION_ID --dry-run
woobe agent '@support' stage --revision REVISION_ID --yes
woobe agent '@support' candidate CANDIDATE_UUID
```

Replace the revision and Candidate placeholders with returned IDs. Networks use
the same commands. Stage requires the selected remote Draft generation and exact
registered working revision. It verifies the local retained executable archive,
reads the server checkpoint and prepares that sealed closure, independent of
current YAML edits. Hydrate a missing executable object before Stage. It does not
compile changed local descriptors, push Source, change native Draft/Staging
selections, publish or activate Production. Existing Provider bindings are
required; credentials are never copied from historical source.

Acceptance reports `state: preparing`, an original operation ID and a Candidate
UUID. Inspect `candidate CANDIDATE_UUID` until preparation is ready; preparation
can wait for Knowledge/MCP dependencies or fail. Use the returned
`preparation_operation_id` with `woobe package status OPERATION_UUID` for phase
diagnostics. A ready Candidate has an exact native snapshot and runtime digest;
it is not a successful Evaluation or a published Release. Candidate publication
and fenced deployment require their separately negotiated contracts.

A lost acceptance response leaves its original operation in private state. Run
`woobe agent '@support' draft reconcile` (or Network) to recover the exact
acceptance without another POST. Reconciliation preserves Draft selection/CAS and
records the Candidate ID; it does not imply preparation succeeded.

`stage` without `--revision` keeps the legacy native current-Draft promotion.
Do not use that legacy command to stage an isolated historical Draft.

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

## Project authority

Project lifecycle policy governs legacy promotion and exact deployments. See [Project lifecycle policy](PROJECT_LIFECYCLE.md) for managed gates, stable Production actors, generation CAS and read-only recovery. Local locks and `--yes` do not weaken this authority.

A completed ASaC operation leaves an empty private checkpoint (`{}`). Binding
recovery accepts this cleared marker. An unresolved operation, partial record
or unreadable/malformed checkpoint still requires reconciliation before recovery.

Server-signed ASaC receipts can be exported and verified offline with an explicit
operator-confirmed root. See [signed receipts](SIGNED_RECEIPTS.md) for trust pinning,
rotation, revocation and limits on freshness and Git provenance.

## Independent Git provenance

An exact commit proof and trusted pipeline receipt are separate from revision,
publication and deployment identities. See [Git provenance](GIT_PROVENANCE.md).
A failed Git/documentary step never repeats activation.

## Unified delivery

See [Deployment](DEPLOYMENT.md) for exact Release/Staging/local delivery, private intent recovery and explicit rollback. See [CI deployment](CI_DEPLOYMENT.md) for deploy-only authority and encrypted checkpoints. Existing commands retain their semantics.

Configuration-aware backends qualify deployment against the exact target
Environment. Preparation of a Candidate artifact can finish while its required
values are missing; check configuration before running its evaluation. A
Production plan retains configuration versions. If a value, declaration or use
policy changes before apply, `CONFIG_REVISION_CONFLICT` requires a new plan after
review. Reuse the same immutable Release; do not republish merely to rotate a
secret. Native promotion and rollback also reject incomplete Production
configuration. Project lifecycle permissions and workflow leases still apply.
