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
