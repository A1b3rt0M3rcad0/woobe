# ADR 0006: Persistent artifact workspaces and document runtime

Status: accepted for implementation; capabilities are not yet implemented.

## Context

Applications need to provision files before starting a conversation and reuse
them across authorized Sessions. Existing Knowledge Collections, immutable
Vector Snapshots, Session history and package archives have distinct purposes;
none is a substitute for a persistent artifact catalog.

## Decision

Introduce one `artifacts` bounded context in Core. An `ArtifactWorkspace` belongs
to a Project and an Environment and survives Session/Run deletion. It is distinct
from the administrative identity Workspace. Its external namespace/key is opaque;
no educational or application-specific entity is required in Core.

PostgreSQL owns metadata, immutable revision identity, catalog history, upload
receipts and processing state. Filesystem/S3-compatible object storage owns bytes.
Original revisions are immutable and verified with SHA-256. Derived text, trees,
tables, figures and summaries name their exact input revision and recipe.

API and existing Workers consume Core through module entrypoints/background
boundaries. Shared application use cases enforce authorization for both direct
API access and Agent/Network tools. External Context selects a Workspace; it
never grants permission. Permissions are intersected across the current
principal, grant, environment, immutable Release and Network node. Revocation
is checked again on subsequent operations, including download and publication.

Session-scoped External Context retains its existing initialize-once contract.
Binding a Workspace does not load all files into model context. Runs pin catalog
versions and record exact sources actually used, rather than snapshotting every
file. Agent/Network Sessions remain usable without an Artifacts binding.

Use bounded catalog/text search, structural trees and on-demand reads. Native
processing/indexing is the default. Docling, OCR and a pinned local PageIndex
adapter are optional worker capabilities, loaded only when selected. No
PageIndex Cloud or required vector database is introduced. Model enrichment
uses a restricted injected gateway and records usage/provenance.

Reuse existing HTTP/MCP execution/security boundaries for typed file transfers;
do not expose object storage credentials, host paths or unrestricted fetch URLs
to Agents. Local idempotency and durable `uncertain` receipts address ambiguous
external side effects; exactly-once external execution is not promised.

Preserve legacy Knowledge locations, Releases, RAG fallback, textual runtime
calls, stream/reattach semantics and `/v1/jobs` behavior. No generic runtime jobs
API is implied by Artifacts processing jobs. Observer remains passive.

WOS, WKS, arbitrary Agent terminals/code execution and application-specific
pedagogical models are excluded. Lipo is a consumer acceptance example, not a
repository to modify. No new mandatory microservice is introduced.

## Delivery and consequences

The implementation follows the attached 60-step contract in
`docs/implementation/artifacts/PLAN.md`, with explicit evidence in its manifest.
CLI and SDK snapshots will be imported in step 02, preserving original licenses,
module/package identities and source provenance. Separate client repositories
remain untouched; synchronization/publication requires a subsequent decision.

All 60 commits belong to one feature branch and one always-Draft PR. This ADR
does not assert product readiness, provider qualification, deployment or release.
The final gate requires real adapters and provider evidence; mocked success
cannot substitute for that qualification.
