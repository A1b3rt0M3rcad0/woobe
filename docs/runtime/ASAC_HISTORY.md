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
