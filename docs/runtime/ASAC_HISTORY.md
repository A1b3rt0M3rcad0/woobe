# ASaC history observations

Native binding recovery reads accepted owner-phase generations independently of
later native observations. Frozen constituents retain their snapshot hash and
source kind in the same owner transaction as acceptance. Reuse can therefore
validate an exact unchanged snapshot without the original actor's export ticket.
Older receipts recover proof only from their original server-retained plan, never
from a newly observed snapshot. The native owner rechecks the snapshot hash before
reuse. Incomplete or contradictory evidence rejects reuse; no latest-version
selection, standalone Agent Draft mutation or credential transfer occurs.

Agent and Network own their lifecycle. Read-only ASaC projections export native
publication and activation identities without modifying Draft, Staging or
Production. Package export remains the closed artifact codec.

Development exports capture an existing Agent/Network ASaC resource UID inside
the owner's authorized SQL snapshot. A fresh local registry reuses that UID,
allowing independent isolated Drafts without inventing a second logical root.
The UID is capture/binding evidence, not destination identity embedded in
portable executable descriptors. Frozen Network constituents keep distinct
local snapshot artifacts. A conflicting established local UID must be resolved
from its original history rather than silently rewritten.

Owner entrypoints expose administrative reads:

```text
GET /projects/{project_id}/agents/{resource_id}/asac/current?environment=production
GET /projects/{project_id}/agents/{resource_id}/asac/history?stream=releases&limit=100
GET /projects/{project_id}/networks/{resource_id}/asac/current?environment=production
GET /projects/{project_id}/networks/{resource_id}/asac/history?stream=deployments&limit=100
```

`current` resolves the actual selection, never the newest version. PostgreSQL
observations use one repeatable-read transaction for authorization, Draft revision
and selected snapshot. Legacy selection has no CAS environment generation:
`environment_generation` is null and `generation_status` is `legacy_unavailable`.
Callers must not manufacture one from dates or release IDs.

History uses separate `releases` and `deployments` streams. Pages contain 1–200
rows ordered by server creation time and ID. An authenticated, scoped cursor
preserves the first page's watermark and refuses alteration or reuse on another
Project/resource/stream. Later publications do not enter an in-progress traversal.
`complete` covers that watermark within `authorized_resource_metadata`, not global
access, object availability or runtime executability. Queries retain owning
Project/resource predicates after the owner gateway authorizes the principal.
Published history requires Production read authority; `current` validates the
explicit requested environment, so a Staging-only grant cannot read Production.

Legacy records preserve original IDs and `unknown_origin`. No chronological parent
chain or Git commit is invented. Publication metadata and activation events are
separate records. Runtime digests retain an explicit native legacy scope; they
are not interchangeable with portable definition or artifact digests.

## Portable digest contract

Python `shared.contracts.asac.asac_digest` and CLI `internal/asac` implement
`woobe-asac@1.0/SCOPE`. A type-tagged ASCII tree represents strings as UTF-8 hex,
numbers as exact reduced fractions, sorted object keys and ordered arrays. This
preserves strings, types, absent/null and precise numbers across Python and Go.
Record digests exclude their own digest field. Existing `woobe-package@1.0`
artifact/inventory canonicalization remains unchanged.

Hashes prove integrity, not authorship. A fetched receipt is an observation over
an authenticated connection; these legacy exports are not signed offline
attestations. Arbitrary Git claims are not verified provenance. Credentials,
secrets, leases and private operation checkpoints are excluded.

This read contract does not advertise isolated Draft lines, candidate evaluation
gates, publication-only Network semantics or fenced deployment. Existing native
mutation semantics remain unchanged; history is not authorization or deployment
preconditions.

## Isolated Draft storage contract

Schema `1.0` adds owner-scoped `/asac/drafts`, `/asac/revisions` and
`/asac/operations/{operation_id}` endpoints for both Agents and Networks.
An isolated Draft keeps the existing native resource identity, a logical UID,
its name, a monotonic generation, verified origin and a retained closed artifact.
Opening `hotfix` lazily records the existing `default` as an unsealed legacy
Draft; it does not replace its content with the hotfix's historical snapshot.
Neither opening, saving nor checkpoint registration changes native singleton
Draft content, Staging or Production.

Writes require the owner's Draft write grant. Opening also rechecks the captured
source environment's read authority. Logical UID/native bindings are unique per
Project; client IDs never grant access. Save requires `expected_generation`.
Registering a revision verifies the exact retained artifact and recomputes its
portable definition/component digests. Parents must already exist under that
same owner identity. Published checkpoint bytes and lineage cannot be replaced.
The operation receipt is committed in the owner's transaction with the Draft
change. Replaying its exact operation ID returns its committed result; another
payload conflicts. A missing receipt reports `not_observed`, incomplete and
`retry_authorized: false`; this is not authorization for a second mutation.

Package owns retained closed objects independently of expiring upload/export
handles. Materialization revalidates inventory, not just metadata. This contract
advertises `isolated_drafts`, `retained_artifacts` and `revision_registration` in
Package capabilities. `candidate_lifecycle` and `fenced_deployment` remain false
until their corresponding lifecycle contracts are available. Saving a closed
object validates its portable schema/inventory; runtime semantic qualification
is explicitly `stage_required`, not a claim of Production readiness.

The `woobe-portable-definition@1.0` digest scope resolves component references to
semantic digests, model credential references to public provider requirements,
and support-file paths to captured content hashes. Package labels, alias keys,
physical paths and destination credential IDs do not determine it. Only captured
Providers participate in checkpoint dependencies. Native runtime-binding digests
remain separate. The Go/Python shared complete-package fixture validates parity.
Development export revalidates captured Draft generations before returning native
bindings, refusing a raced capture instead of associating old content with a
new generation.

Native identities with retained ASaC history cannot be physically deleted. Agent
archiving remains the supported retirement path; Network deletion already refuses
version/runtime history and now includes retained ASaC history in that refusal.
This preserves immutable references rather than cascading their deletion.

### Optional author source digest

Revision records may include `author_artifact_digest`. The record digest includes
this optional field when present; records without it retain their existing hashes.
The server validates the executable closed object and declares author source as
`declared_not_retained`: it does not possess or attest the author's YAML bytes.
Capabilities advertise `author_digest_declarations` so clients negotiate this
extension before registration. Author source does not grant authority or replace
executable digest validation. Checkout must independently compile and validate
retained source before changing local files.

## Accepted synchronization generations

The Package synchronization registry records each completed native phase's
`accepted_native` generation with its operation ID and definition digest in the
same owner transaction as the mutation and receipt. A later registry read
returns `revision`/`accepted_revision` from that accepted evidence and a separate
`current_revision`. `binding_status: resource_changed` means another edit occurred
after acceptance; it must not advance the client's accepted content base.
Frozen dependencies report `frozen_snapshot` and retain their exact snapshot ID.

The capability `asac.accepted_binding_generations` announces this contract.
Legacy rows report `generation_scope: legacy_current_observation` and
`accepted_generation_unavailable`; their observed current generation is not proof
that the recorded definition was accepted at that generation. This endpoint does
not grant permissions or restore credentials. Authority is checked for every
native binding during traversal; a failed authority or receipt consistency check
prevents claiming a complete registry.

Registry traversal uses a repeatable transaction snapshot on PostgreSQL. If a
later operation has reserved/prepared a binding but has not accepted its new
definition, the registry reports `generation_scope: unsealed_native_binding`,
`binding_status: binding_incomplete` and no accepted revision. It does not combine
the earlier receipt's definition with the partially prepared native generation.

## Isolated revision metadata catalog

`GET /projects/{project_id}/agents/{resource_id}/asac/revisions` and the Network
counterpart list immutable revision records under the native owner's current
read authority. Pages use an authenticated resource/kind scope and fixed
watermark. PostgreSQL reads use a transaction snapshot; records appended after
the first page are fetched in the next traversal. Limits are 1–200 per page.

The catalog verifies persisted record digests and identities. It is metadata
coverage for the authorized resource, not a global-history claim. Executable
objects are not loaded by this endpoint; missing author objects remain
`declared_not_retained` or `unavailable`. The capability `asac.revision_catalog`
advertises support. Neither listing nor its CLI mirror moves a Draft head or
changes native Draft, Staging or Production.


## Retained executable hydration

Owner-scoped GET endpoints at `/asac/revisions/{revision_id}/artifact/receipt`
and `/artifact` transfer an immutable retained package. The owner validates
record integrity, checks current read authority, delegates bounded archive
verification to Package, compares artifact/definition digests and rechecks
owner authority after I/O. No transaction spans archive encoding. Transfers
are deterministic, bounded to 128 MiB and carry transport, record and artifact
digests with `Cache-Control: no-store`. Missing bytes are reported as
`ASAC_OBJECT_UNAVAILABLE`; metadata remains independently queryable.

The capability `asac.retained_object_hydration` advertises this protocol.
Hydration does not restore author YAML or native credential bindings, move a
working head, or qualify runtime execution. Author-source availability remains
separate from executable-object availability.


CI backend validation has a 90-minute job budget because the shared Docker
host can spend up to 40 minutes acquiring its exclusive validation lock. The
complete test contract still runs after acquisition; lock wait limits, checks
and assertions are unchanged. This budget avoids reducing a 25-minute suite
to a few minutes when another required container/acceptance job owns Docker.

### Exact author source custody

`asac.author_source_retention` advertises bounded gzip/JSON author uploads and
Agent/Network-owned revision source transfer. A canonical author object preserves
original YAML/comments and declared support bytes, separately from the compiled
closed object. Both formats and hashes are checked before custody. Upload tickets
are actor scoped with a 24-hour registration window; an accepted revision link
retains source independently of ticket expiry and uploader identity. Owner read
permission and Project read permission are rechecked around storage I/O.

Checkpoint registration matches the author digest, Root UID and complete component
UID/key mapping, rechecks the selected Draft generation, and records the retained
link with the owner receipt in one transaction. Replays recover their original
receipt. Custody is explicitly **not** a server compiler attestation. The CLI
verifies recovered YAML/support files and uses the recorded compiler recipe to
compare the complete source closure with the sealed executable definition before
publishing local source. This transfer changes neither working files, selected
revision, native bindings nor Production. A separate guarded checkout restores
source. Legacy declared-only revisions remain executable-readable and explicitly
report unavailable source. Migration `0084` adds nullable retained source links
and Package-owned source custody rows without rewriting historical record bytes.

## Detached native candidate preparation

`asac.candidate_preparation` advertises POST `/asac/candidates` and GET
`/asac/candidates/{candidate_id}` for both Agent and Network. Stage selects an
exact registered revision from an isolated Draft with its expected generation.
The server verifies the retained executable object, Root/component identities,
scoped native bindings and current grants. It accepts the durable native Package
operation, candidate ledger and original Stage receipt in the same owner SQL
transaction. Object I/O and semantic planning occur outside that transaction;
source generation and authorization are checked again before acceptance.

The acceptance receipt is **preparing**, never ready or published. Durable native
phases create detached immutable Agent snapshots and a Network snapshot with
exact constituent candidate IDs. Final verification seals readiness and its
runtime digest in the original native receipt transaction. Native singleton
Draft, Staging and Production selections are unchanged. Database guards reject
updates/deletes of candidate snapshots, including through legacy persistence.
Partial preparation can be inspected through the returned Package operation and
resumed through that original operation; it cannot announce an incomplete root
as ready. Lost HTTP acceptance is recovered from the original owner operation
receipt, never by creating a second Stage identity.

Stage reads the sealed object, not current author files. The registered revision
and selected isolated Draft must agree; a divergent current working file is not
silently recompiled under that revision. Provider requirements need verified
private destination bindings. Protected values are not created or copied from
historical credentials. External Knowledge references currently need explicit
binding support; closed portable Knowledge remains supported.

CLI commands are `agent|network REF stage --revision rv_UUID --yes`, its read-only
`--dry-run`, and `agent|network REF candidate CANDIDATE_UUID`. The companion CLI
normalizes inspection output and checks response owner/protocol identity. This
phase does not provide evaluation, publication or Production promotion;
`candidate_lifecycle` and `fenced_deployment` remain false until their actual
protocols and gates are implemented. Migration `0085` preserves historical
revision bytes and adds owner candidate ledgers, verified revision component maps
and immutable native candidate guards. Its downgrade refuses retained candidates
instead of removing their protection.

## Versioned Candidate evaluation

Owner routes accept `POST /asac/candidates/{candidate_id}/evaluations` with an
operation UUID and a strict suite, expose `GET /asac/evaluations/{evaluation_id}`,
and reconcile original Runs through `POST /asac/evaluations/{evaluation_id}/reconcile`.
Agent and Network scopes require current `run:execute` for acceptance/reconciliation
and `run:read` for inspection. Query parameters cannot change the staging authority.

The original acceptance, planned native Run identities and suite/content digests
commit together before provider I/O. Replaying the operation returns its original
accepted receipt without another execution. Qualification is a separate owner
ledger backed by exact native snapshots, current binding fingerprints and terminal
SQL/journal evidence. Missing or conflicting evidence cannot pass. Network case
Runs invoke frozen child Agent candidates through an internal server-only grant;
public metadata and ordinary sessions cannot grant candidate execution authority.

Suite/dataset/policy versions are declarations, not attestations. Server-verified
content digests bind them to the actual bounded suite. Only `all-cases-pass@1` is
supported; expected output uses typed canonical comparison. Failures and costs
come from actual native Runs, never client-supplied success flags. SQL migration
0087 protects accepted identity, planned case Run IDs and terminal evidence from
mutation/deletion. Provider exception messages are not exported.

`asac.candidate_evaluation` advertises this protocol. Publication, activation and
fenced deployment remain separately gated until their complete implementation.

## Exact evaluated Agent publication

`asac.candidate_publication_kinds: ["Agent"]` advertises owner routes
`POST /asac/publications` and `GET /asac/publications/{publication_id}`. The strict
request names an original operation, ready Candidate and passed Evaluation plus
an audit reason. It cannot assert successful evaluation or verified Git status.
Write authority is `agent:version` at Staging; inspection requires `agent:read`.

The server verifies retained revision/object identity, complete passed native Run
evidence and matching record/runtime/binding digests. It refreshes destination
bindings before acceptance, then rechecks authority, readiness and evidence under
the owner root lock. Native Release insertion/reuse, immutable publication ledger
and the original operation receipt commit in the same transaction. The selected
Candidate remains the source even when current native Staging changed afterward.
Default Draft, Staging and Production selections are untouched.

Native runtime hashing retains canonical primary and fallback Provider Model IDs,
matching the candidate/runtime repository rather than the legacy mapper projection.
Identical native executable content may reuse an immutable Release; a new intentional
publication still has separate revision/evaluation provenance. Replaying the original
operation returns its original result and does not allocate another Release.

Migration `0088` adds immutable Agent publication records and seals ready/rejected
Agent/Network Candidate ledgers. Downgrade refuses retained publication records.
The receipt digest verifies content integrity; Git is declared/unavailable and
receipts are not yet signed offline attestations. Network exact publication and
fenced deployment are not advertised by this phase. Legacy Network publication
retains its Production activation behavior.

The CLI saves pending identity before acceptance and writes an append-only,
destination-scoped documentary receipt afterward. Local mirror failure cannot
roll back a remote commit and does not authorize a second publication. Read-only
original-operation reconciliation retries the local mirror without another POST.

### Versioned Network runtime identity

New Network Candidates advertise `network-execution-runtime@2` and retain that
scope in their ledger (`0089`). Historical Candidate hashes and native
`composition_hash` values remain unchanged. Native composition hashes include
exact stored snapshot selectors; the ASaC execution identity includes topology,
settings, full constituent execution hashes, frozen overrides and effective
external context, excluding only lifecycle copy IDs/version/status metadata.
The legacy override's `pinned_release_id` repeats the loaded snapshot selection
and is excluded; executable overrides and unknown future fields remain included.
This allows an exact immutable constituent copy to preserve execution identity
while retaining distinct storage identities. Source/Release ownership and content
must still be independently verified. Scope is unavailable for older ledgers;
it is never silently asserted or rewritten. Shared Go/Python digest fixtures
cover the normalized payload, and differential tests reject changed content,
missing closure, wrong ownership and unsupported selectors.

The Agent-owned frozen publication gateway is internal composition infrastructure,
not a client HTTP endpoint. Each constituent copy verifies current Agent authority
and exact snapshot hash, uses the existing Agent transaction owner, and commits
its native Release plus original parent-scoped operation receipt together. It
never changes standalone Agent environment selection. The Network publisher will
coordinate these receipts through its own durable preparation and finalization;
this foundation does not yet advertise exact Network publication.


## Exact Network publication and durable constituent preparation

Migration `0089` retains Candidate runtime scope. New Network Candidates use
`network-execution-runtime@2`: graph and routing, complete semantic child runtime
digests, overrides and effective external-context contracts remain executable
identity; immutable lifecycle reference IDs/versions are storage identity. Legacy
Candidate evidence is not rewritten; prepare and evaluate a new scoped Candidate.

`asac.candidate_publication_kinds` now includes Agent and Network. Exact Network
publication requires its frozen ready Candidate and passed exact Evaluation,
current `network:version` plus constituent `agent:version` authorization and fresh
binding fingerprints. It does not read current Staging as publication source or
change Production/native Draft/Staging/standalone Agent selections.

Network accepts an original operation/preparation before calling the Agent-owned
frozen-publication gateway. Each child copy has a deterministic original operation
identity; reuse and immutable receipts commit in its Agent owner transaction.
The final Network Release, publication receipt, constituent retention references
and preparation terminal state commit together in the Network owner transaction.
No transaction spans provider IO or another owner's write.

`GET /asac/publications/{id}` exposes preparation counts or immutable publication.
`POST /asac/publications/{id}/reconcile` resumes only the original preparation,
reauthorizing and checking Candidate/Evaluation/bindings before each child and
final commit. `POST /asac/publications/{id}/cancel` with a reason seals unfinished
preparation without deleting already copied immutable children. Original accepted
operation receipts never change; a replayed original POST returns that acceptance,
not a second execution. Cancellation cannot undo a final published Network.

Migration `0090` protects publication/constituent ledgers, original operation
receipts and executable content of retained native Releases. Preparations allow
append-only child observations and terminal transitions. References retain child
snapshots even across partial failures. Downgrade refuses retained evidence.
Existing Production activation metadata is distinct from immutable executable
content. This phase still does not implement fenced deployment or signed offline
server attestation; Git remains declared and local mirrors are authenticated-fetch
observations with content-integrity checks.

Regression coverage includes real PostgreSQL publication, direct tamper attempts,
controlled final-commit failures, original replay, deterministic child reuse,
resume/cancel and unchanged standalone environments. CLI recovery mirrors terminal
publication/cancellation only after reading original acceptance; it never repeats
publication on an uncertain outcome.

## Monotonic native environment selection generations

Migration `0091` adds owner-scoped Staging/Production selections. Deferred native
PostgreSQL triggers observe each transaction's final native selection, covering
legacy promotion/rollback writes as well as future ASaC activation. A temporary
status demotion/promotion in one transaction is not counted as two deployments.
A -> B -> A advances twice even though the final Release ID equals the first.
Read-only current queries never initialize or increment generation.

Existing selections bootstrap at generation 1 (unselected environments at 0).
This does not fabricate historical deployments or their missing generations.
Native snapshot changes also advance a retained internal storage fingerprint;
it is not a competing public semantic runtime digest. Counter rollback, deletion
while its root exists and identity replacement are rejected by PostgreSQL.
Root deletion still follows native retention rules. Downgrade refuses nonzero
retained generations.

Current reads verify the selection against the same repeatable-read native
snapshot and expose `generation_status: monotonic_owner_selection`. Missing or
mismatched state raises `ASAC_SELECTION_INCONSISTENT`, never a misleading CAS-safe
observation. Draft lines retain their separate authoring generations. Capability
`environment_generation_scope: monotonic-owner-selection@1` lists supported
Staging/Production environments. Activation plans/fencing are a subsequent
contract; these counters alone do not grant or enforce activation authorization.

## Bounded workflow leases

Migration `0092` adds owner-scoped lease cells and immutable original-operation
receipts for Agent and Network. `GET /asac/leases` observes a reservation;
`POST /asac/leases/{acquire,renew,release,break}` requires typed scope and stable
operation identity. Scopes are resource authoring, a specific isolated Draft,
native default Draft, Staging or Production selection. Resource authoring leases
cover isolated Draft writes; they do not block reads, tracing or frozen Runs.

Workflow UUID, lease UUID and positive monotonic fencing counter identify the
reservation. Reusing a CLI Key does not imply ownership or reentrancy. Database
time decides expiry. Requested TTL and total duration are bounded by
`WOOBE_ASAC_LEASE_MAXIMUM_TTL_SECONDS` (300) and
`WOOBE_ASAC_LEASE_MAXIMUM_DURATION_SECONDS` (900). Renewal cannot extend the
original maximum. An expired workflow cannot renew or silently acquire a
replacement. Reacquisition creates a new lease identity and increments fencing.
Administrative break requires `project:access:write`, a meaningful reason and
the exact current lease/fencing pair; it cannot accidentally break a replacement.

Isolated Draft open/save/checkpoint requests optionally carry `leases` with the
exact active authoring proofs. The owner checks them before artifact I/O and
again in the short transaction that writes. Deferred PostgreSQL commit guards
recheck database time, closing expiry between validation and commit. Old proofs
are rejected even when the reservation has already expired. CAS remains required.
A replay reads its original accepted receipt after current authorization; it does
not revive the reservation or perform a second write.

Legacy native authoring writes cannot bypass an active authoring reservation.
Their old schemas do not transport isolated-workflow proofs: release the owned
reservation explicitly or use the isolated Draft protocol. Native Draft leases
must therefore be acquired only with an intentional understanding of this gate.
Staging/Production lease storage is available for the forthcoming explicit
activation protocol; this change alone does not turn legacy activation into a
fenced deployment or enforce a managed Project policy.

Operational proofs belong in private `.state`, never portable author lockfiles,
Git or skill assets. `fencing_token` is a numeric concurrency counter rather than
an authentication secret. Lease conflict/expiry database errors return safe
409 diagnostics without SQL or private bound parameters.

## Exact fenced Release selection

Candidate publication and environment selection are distinct. Agent and Network
owners retain immutable deployment plans fixing an evaluated published Release,
Candidate/Evaluation evidence, runtime fingerprints, expected monotonic environment
generation, previous pointer and audit reason. Planning does not activate.

Applying a plan requires current environment authority and an exact short
Staging/Production workflow lease. Recheck retained qualification, current binding
versions, runtime identity, expected generation and the database-clock plan deadline
before the owner transaction changes selection. Hold destination binding versions
through commit. Resource-authoring reservations are independent and do not grant
selection authority. Original-operation replay reads retained acceptance rather
than applying a second transition.

The owner commits independent selection, native Production history when changed,
immutable deployment receipt, original operation acceptance and outbox together.
Deferred PostgreSQL guards recheck plan/selection/receipt/outbox consistency and
lease expiry at commit, including expiry after SQL mutation. Outbox delivery state
can advance, but its evidence payload cannot change. A new audited selection of
an unchanged executable keeps the same environment generation.

An Agent selection uses a separate pointer rather than rewriting Release status;
Staging and Production can select the same immutable Release. Runtime admission,
current inspection and environment export resolve this owner pointer. Network
selection changes only the native environment pointer and leaves the Release's
closed constituent bindings unchanged. Once an environment uses ASaC selection
authority, legacy writes to that selection reject with `ASAC_SELECTION_MANAGED`;
create an exact deployment plan instead.

This owner selection protocol is separate from Project-wide managed lifecycle
policy, Web editor integration, signed offline receipts and Git verification.
Those features must not be inferred from an accepted deployment receipt.

## Web environment selection

Cards, Playground, lifecycle views, API references and Runtime Key dialogs read
`/asac/current?environment=staging|production`. A snapshot's persisted `status`
is not an environment assignment. This read works for both legacy and ASaC
selection authorities; no frontend fallback selects the newest Release.

The Web shares a Project/kind/resource/environment query with a 15-second stale
window, 30-second polling while visible, and refresh on mount/window focus.
Lifecycle writes invalidate selections, immutable details and runtime settings.
Authentication changes clear the query cache. Late responses for another Project
or resource cannot replace the active query. This observation is for presentation;
deployment planning still obtains a fresh owner read and the backend enforces CAS,
leases, authorization and managed lifecycle policy.

A complete verified null selection means **not deployed**. Loading, authorization
failure, timeout, incomplete responses and server errors remain checking/unknown.
A verified snapshot ID remains selected if its detail GET is forbidden; the UI
shows that ID and a retry action rather than claiming absence. Playground needs
the exact selected snapshot's details before constructing a Run or Session:
provider/model, session mode, strategy and external context come from that
immutable snapshot. Runtime enabled/disabled is read independently and unknown
runtime settings do not enable the composer. Publishing a Release and deploying
it are distinct actions; immutable Release status is never rewritten to repair UI.
Runtime Key creation retains the chosen environment instead of switching to
Staging when Production is empty or unreadable. Existing server authorization
and key issuance rules are unchanged.

The Agent list makes one Agent list request and **three small requests per card**:
two current-selection reads and one runtime-environments read. It no longer
fetches complete Release catalogs or immutable details for cards. The old card
made two requests (runtime plus full Release catalog); this change reduces
snapshot payload exposure, not request count. Shared queries deduplicate reads
across mounted consumers. This is not a load/capacity benchmark or a bulk endpoint.
Overview's current Agent counts and recent selected Releases also read the owner
selection, including a single immutable Release selected in both environments.
ASaC display timing uses the selection's update timestamp; legacy selections retain
native promotion timestamps. Publication dates remain the immutable creation date.
Network-pinned constituent bindings remain distinct from standalone Agent
selection. Initial deployment labels use the absent previous selection; retained
activation records are not modified.

## Project lifecycle authority

Core owns `GET/PUT /core/projects/{project_id}/lifecycle-policy` and read-only
`GET /core/projects/{project_id}/lifecycle-policy/operations/{operation_id}`.
An absent policy is explicit legacy mode, generation zero. Updating policy
requires `project:access:write`, a stable operation UUID, expected policy
generation, `managed`, optional `production_actors` and a meaningful audit
reason. Core records the resulting policy, before/after generations, principal,
server database time and immutable original-operation/outbox receipt together.
A distinct accepted policy operation increments generation even if settings are
unchanged; replay of the original operation returns its original receipt.

`production_actors` optionally restricts Production planning/application to
stable `user:UUID` / `control:credential-UUID` identities. It never grants
resource permission and does not authorize a CLI key secret or a rotated key
row. Empty restrictions retain ordinary environment/target grants. Policy
changes invalidate plans captured under a different policy digest. A Project
row lock also fences first policy insertion; the Core public reader holds policy
through final owner deployment commit.

Managed mode rejects legacy Agent/Network Staging/Production promotion at the
persistence boundary, including legacy Web and materialization paths. New
immutable native Releases require exact ASaC publication evidence (Network
constituents retain their original Agent-owner receipts). Draft authoring,
history reads and already admitted executions remain separate from selection.
The gate returns bounded domain conflicts; local `force`/`--yes` cannot disable
it. Administrative policy changes are explicit, audited CAS operations.

CLI 0.30+ exposes `project lifecycle show`, YAML/JSON `update` and read-only
`operation UUID`. These commands do not require a development registry. The
CLI verifies route advertisement and keeps a stable original operation for
recovery rather than repeating an uncertain write under a new identity.
Project policy does not replace signed offline receipts, Git attestations,
Web isolated-Draft UX or runtime continuity work.

For optional instance-signed owner receipts, configure an online signing key
and an offline-root-signed public manifest as described in
[signed ASaC receipts](ASAC_SIGNED_RECEIPTS.md). The API never holds the offline root seed.
Existing authenticated history reads do not automatically establish offline
trust; clients pin an independently confirmed root fingerprint.

## Web isolated-Draft workbench

Agent details and the Network workspace expose **History & lifecycle**. The
workbench opens a named isolated Draft from an authorized Draft, Staging,
Production or fixed Release capture. Opening a line, saving author files,
checkpointing, preparing a Candidate and publishing a Release do not select
Production. Native resource identity is reused; an isolated line is not a new
Agent or Network.

The editor exposes bounded UTF-8 files from the retained closed Package. The
Package manifest and binary/oversized files remain read-only. A save rebuilds the
canonical graph, checks schemas/references and retains a new immutable object.
It uses the selected Draft's exact generation. Semantic preparation remains a
separate Stage operation; a valid YAML document alone does not qualify runtime.

A checkpoint computes definition/component identities on the server and records
explicit parents. Stage prepares that exact checkpoint using authorized captured
native bindings. Candidate readiness and worker evaluation are observed by ID.
Publishing requires evidence for this Candidate, leaves Production unchanged and
does not invent Git provenance. Production/Staging activation requires a reviewed
plan with expected environment generation and a private environment lease. The
Project policy and owner permissions apply to these paths as they do to CLI.

Metadata refresh never replaces editor files. A remote generation conflict keeps
local edits and blocks saving; compare remote files or download local author files
before explicitly discarding/reloading. Local editor text is not written to
browser storage. Private lease proof is held in browser memory only. Do not close
the editor with unsaved files without saving or downloading them.

Before each owner mutation the browser stores only original operation UUID,
action and generation in session storage. A lost/uncertain response blocks new
writes. **Reconcile original operation** performs a read-only lookup; unobserved
results never authorize another POST. Source capture/current-selection preflight
failures occur before this checkpoint. Refresh/reload can recover an original
accepted operation; lost volatile deployment context must be inspected/planned
again, and any abandoned lease expires according to the server clock.

Editor requests are `GET/PUT .../asac/drafts/{draft_id}/editor`, checkpoint is
`POST .../checkpoint`, and Web Stage is `POST .../stage`, for both owner kinds.
They delegate to the canonical Package and lifecycle owners rather than a second
Web publication engine. `origin.authoring_channel` is derived from authenticated
principal type (`web` human session or `api` Control Key); it is not an attestation
that a particular UI or Git workflow was used.

Trusted Git origin has an independent append-only authority path; see
[Git pipeline provenance](ASAC_GIT_PROVENANCE.md). Declared publication metadata
is never silently upgraded or rewritten.

## Acceptance and Run continuity

The [acceptance matrix](../testing/ASAC_ACCEPTANCE.md) maps H01–H35 to regression coverage and separates live integration from unit checks. [Accepted Run identity](ASAC_RUNTIME_IDENTITY.md) documents native Session continuity and the exact admission/binding digest scopes.

## Environment tests and capture diagnostics

Agent administrative tests in Staging/Production validate the authoritative ASaC
selection under an environment row lock. A selected immutable Release remains
`release` kind, including when selected in Staging; it is not copied or relabeled.
A stale selected UUID is rejected. Without ASaC selection, legacy snapshot-kind
validation remains intact. Runtime execution still uses the exact tested snapshot.

Portable Network captures return bounded `PACKAGE_EXPORT_NETWORK_*` conflicts
for incompatible definitions, graph integrity, unavailable bindings or incomplete
constituents, with `/spec` or node paths. They never reveal provider exceptions or
substitute latest dependencies for a pinned snapshot. Agent PATCH rejects unknown
top-level fields rather than silently discarding them; advertised schema validation
exposes `additionalProperties: false`.


## Incomplete captures and accepted closure recovery

A missing native registry identity at Stage returns
`ASAC_CANDIDATE_BINDING_UNAVAILABLE` with the affected component descriptor and
`/metadata/key`. Canonical create plus capture does not prove accepted registry
closure. Inspect bindings recovery in dry-run, explicitly bind destination
Providers and use managed push to establish the accepted closure, then refresh
and checkpoint the isolated Draft before preparing a new Candidate. A rejected
preparation creates no Candidate/accepted operation; uncertain acceptances still
require original-operation reconciliation.

A Network constituent missing a complete primary/fallback ModelSpec adds
`/spec/model/primary` or `/spec/model/fallback` to its node diagnostic. Exact
historical captures never rebuild that evidence from the latest Provider Model.
For mutable author state, repair the Agent configuration and save/rebind a new
Network Draft explicitly. For incomplete immutable history, preserve the old
snapshot and prepare/evaluate/publish a new complete closure. These diagnostics
identify an inspection path; they do not repair operator data automatically.

## Configuration-aware portable definitions

Package 2.0 uses `woobe-portable-definition@2.0`. Component, Provider and root
hashes use distinct versioned domains. A Model resolves its connection alias to
public Provider metadata and typed authentication references. The root includes
all captured connection intents and configuration declarations, sorted by key;
connection display names, alias labels and declaration order are presentation.
Changing an authentication key, endpoint or validation rule changes the sealed
meaning. Values, use-policy grants and destination IDs are never portable intent.

Package 1.0 retains its original digest algorithm and fixtures. Capabilities keep
`asac.definition_digest_scope` at 1.0 for existing clients and advertise both
entries in `asac.definition_digest_scopes`. Registration, custody, hydration and
Candidate preparation compare the record's scope with the verified artifact;
a valid record hash cannot relabel schema2 bytes as scope1. Author compiler
recipes remain retained: schema1 uses the existing `@2.0` recipe, schema2 `@3.0`.

Managed schema2 pushes remain structural Draft synchronization. Candidate Stage
is a separate, explicitly authorized preparation of a sealed revision using
existing destination bindings. It cannot declare keys, create connections or
populate values incidentally. Configuration declaration and Provider binding
revisions are fenced separately from runtime material versions. A prepared
Candidate does not establish configuration readiness, successful evaluation,
publication or deployment.
