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
