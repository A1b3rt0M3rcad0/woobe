# ASaC history observations

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
