# Run-pinned Artifact sources

Artifact-enabled runtime requests carry the Workspace and catalog snapshot resolved
at Acceptance. Session-scoped bindings keep the Session's first catalog version;
run-scoped bindings resolve the current version for each accepted Run. Both Agent
and Network paths still resolve the logical key and recheck current grants before
execution.

File pages and search requests use the accepted catalog version. Signed cursors
include that version, so a cursor cannot move to a newer catalog. Exact revision
and SourceRef reads preserve the referenced revision and representation/index IDs.
Current authorization is checked for every read. A retained revision remains
readable after a later head update, rename, or deletion when it was visible in the
Run's accepted catalog. Purged workspaces, unavailable generations, and revoked
access fail as unavailable or denied; reads never fall forward to `latest`.

The internal Run facade does not accept a caller-selected Workspace or catalog
version. It creates pinned list/search/read requests from the accepted binding.
Search results returned to a Run and source text successfully read by a Run are
recorded in `artifacts.run_source_manifests` and `artifacts.run_sources`. The
manifest is fixed to one catalog version per Workspace and Run, deduplicates exact
SourceRefs by a canonical SHA-256 fingerprint, and grows only with consumed
sources. It contains no file bytes and does not copy the Workspace catalog.

Read-your-writes is explicit: the Run must supply the exact revision receipt, and
the revision must carry the same Run ID. A Node-authored output also has to name a
Node in the trusted allowed-output set. This lets an authorized child Node read a
passed ArtifactRef without exposing concurrent writes from the rest of the
Workspace.

The implementation is validated by unit checks for catalog/cursor pinning and
capability reduction, and PostgreSQL checks for fresh/populated migrations,
manifest deduplication/isolation, historical revisions, and exact Run-output
overlays. See `PROGRESS.md` for the commands and outcomes.

## Typed runtime content

Agent and Network requests may carry ordered `content_parts` containing text and
exact `{artifact_id, revision_id}` references. Legacy `message` strings remain
accepted and their text projection stays available in existing response fields.
Sending both forms together is rejected at the public boundary. Image-only parts
are valid input syntax; an Agent model operation must advertise a matching input
capability before it can consume them.

Before an Agent provider call, the runtime checks the current `read` grant, the
accepted Workspace binding and catalog version, exact revision availability, and
any declared media-type hint. It stores typed references in Agent messages and
execution metadata, and in Network messages/execution snapshots. These records
contain no bytes, base64 data or signed URLs. Network retries, reattachment and
reruns reuse the accepted parts; an idempotency key cannot be replayed with
different content.

Authorized non-image Artifact references are now exposed to Agents through a
bounded, stable set of internal Tools: list, inspect, search, outline, read,
write and process. The effective Workspace, accepted catalog version, principal,
Run ID and Network Node ID come only from the accepted runtime binding; Tool
arguments cannot select a different scope. Search and source reads use the same
Artifact application services as the direct API and record exact sources for the
Run. Writes use the existing upload receipt and deterministic operation identity.
Processing returns its durable job ID and current status without polling.

Document references stay as identifiers until a Tool reads or searches them;
only bounded extracted text excerpts are returned to the model, never raw file
bytes or base64. Image references are resolved through a separate exact-revision
read path after the selected ModelSpec and provider adapter pass visual-input
checks. The Agent treats retrieved document text as untrusted source material.
No provider-specific API key or OpenAI binding is part of the Artifact Tool
adapter.

Visual input accepts only exact PNG, JPEG, and WebP revisions. The current limits
are four images per Run, 4 MiB per image, and 8 MiB combined, further reduced by
the effective model's declared `max_input_bytes`. Authorization and catalog
visibility are checked again before each bounded read, and both the revision
checksum and media signature are verified. Each consumed image is added to the
Run's exact SourceRef manifest.

Image bytes are not stored in chat history, runtime snapshots, logs, or public
events. Provider adapters translate them into provider-specific message blocks
only immediately before invocation, and log previews show text blocks only.
OpenAI-compatible and Anthropic adapters have deterministic contract coverage;
other adapters must explicitly declare and implement the same capability. A
missing capability, adapter, grant, revision, checksum, or size budget fails
before the provider call. No PDF pages are selected automatically; callers must
reference individual rendered images/pages.

Document exploration is bounded to 24 Artifact Tool calls and 64 KiB of returned
UTF-8 source text per Run. Each read is clamped before storage access, repeated
reads of the same exact SourceRef/offset are served from the Run-local cache,
and `next_offset`, `truncated` and coverage remain explicit. Tool results carry
`untrusted_document` context metadata through compaction and recovery; the
context instruction asks the Agent to open exact source excerpts and report
partial coverage. The limit counts bytes actually returned and does not invent
token or multimodal usage estimates.

Successful internal writes persist through the existing Artifact receipt before
the durable `artifact.available` event is recorded. The deterministic operation
identity lets a retry recover the same revision if event recording fails after
the write. Public live/replayed projections allow only exact revision metadata;
file bytes, credentials and raw Tool results are excluded. Synchronous Agent and
Network results, stored assistant messages, terminal journal payloads and
reattached `run.state` expose the same versioned `output_artifacts` and exact
`source_refs`. Projection upserts by Artifact and revision, so replaying an
availability event does not create duplicate outputs or invoke the model again.

Image generation is a separate one-shot `image.generate` ModelOperation behind
the internal `woobe_artifact_generate_image` Tool. The effective ModelSpec must
explicitly declare the operation, image output, allowed sizes, per-call count,
total output byte ceiling, output format and provider idempotency-key support.
Tool schema limits are built from that ModelSpec. A Run can publish at most four
generated images. The adapter uses the Agent's existing approved provider
credential and HTTPS destination; no OpenAI account or OpenAI-specific key is
required. Unsupported provider/model capabilities fail before dispatch.

The provider receives one bounded request with retries and redirects disabled.
Responses must contain complete base64 image bytes; remote URLs are never
fetched. The runtime enforces the total ModelSpec byte limit, PNG/JPEG/WebP
signature and decoded image dimensions, then writes each image through the
normal quota-enforced Artifact output path. The persisted revision includes a
SHA-256, producer Tool, Run, provider request reference and the Run's exact
SourceRefs. Only ArtifactRefs, sizes, hashes and reported usage leave the image
boundary; image bytes and base64 never enter chat history or Run events.

Pending, completed and uncertain operation states are durable Run events. A
deterministic provider idempotency key and per-image Artifact operation IDs let
recovery retrieve the same provider result and publication receipt after a
lost acknowledgement; providers must explicitly guarantee that contract in the
ModelSpec. Unknown results are never blindly dispatched again within a Run.
Multiple outputs are published only after each one independently passes image
validation and the Artifact write path. Provider token/cost usage is returned
only when reported and is preserved in the internal completion journal event.
Peer-contract tests exercise adapter behavior and persistence idempotency; no
live provider call or OpenAI credential is needed to validate this capability.

Automatic Knowledge retrieval can be explicitly set to `none` for an artifact-only
Agent. That selection skips vector binding preparation and never calls embeddings
or RAG; it does not delete stored KnowledgeVersions, Collections or snapshots.
Artifact Tools remain usable only when their own Workspace grants allow them.
Omitted Knowledge strategy continues to mean `rag` for old Agents and Releases.
Package 2.0 preserves an explicit `none` selection without creating or exporting
an unused vector resource; Package 1.0's schema and digest remain unchanged.

Configured HTTP Tools can bind an input field to an exact Artifact reference in
`bytes`, `multipart`, or `url` mode. The Agent only supplies the revision ID;
Woobe resolves it through the accepted Workspace and checks both current `read`
and `transfer` authorization. Bytes and multipart bodies stream from local/S3
storage with size, media-type and SHA-256 checks. URL mode is available only when
the storage adapter can issue a public HTTPS S3 URL; it is short-lived (at most
60 seconds), inserted only into the body sent to the configured HTTPS Tool
destination, and scrubbed from Tool results. Redirects remain disabled and the
normal DNS/egress checks still apply.

Transfer operations have a deterministic ID and durable Run journal events for
pending, completed, failed and uncertain outcomes. Receipts contain exact input
references, hashes, sizes, the destination host and response status, never bytes,
credentials or the signed URL. A configured remote idempotency header receives
that operation ID. If transport acknowledgement is lost, the outcome remains
uncertain and the runtime does not automatically replay the external effect.

MCP Tools can bind an input field to an exact Artifact reference when the selected
peer Tool was discovered with a compatible `format: byte`/base64 or `format: uri`
string schema. Each file call reissues `tools/list` through the same configured
MCP endpoint and session, and compares the peer schema with the frozen discovery
schema before resolving bytes. Base64 transfer is capped at 4 MiB. URL transfer
requires the current Run's `read` and `transfer` grants and a public HTTPS URL
that expires within 60 seconds. Local paths, storage URIs and unbound fields are
never sent as file contents.

Transfer events share the durable `artifact.transfer.*` contract and contain only
the operation ID, exact revision, size/hash, peer host and outcome. Signed URLs
are scrubbed from MCP output and errors. A lost acknowledgement is uncertain and
does not trigger a second Tool call. MCP `isError` remains a failed Tool result.
`resource_link` results are read using `resources/read` on that same configured
peer; at most four links and 64 KiB of text per resource are returned. External
filesystem links, oversized/binary content and nested raw payload fields are
omitted. Existing text-only MCP Tools continue through their original call path.

Configured HTTP Tools can also bind one bounded external result as a new Artifact.
The binding selects a logical Workspace path, accepted media types, maximum size,
and either a binary response body or a base64 field in the configured JSON result.
Optional checksum, application-status, and remote-operation fields are validated
before publication. MCP outputs can bind one schema-negotiated resource from the
same peer session. Result bytes and base64 fields are removed from the model-facing
Tool result after the Artifact receipt is created.

For explicitly configured asynchronous HTTP operations, a status pointer and
allow-listed pending statuses let a Tool return a remote operation reference
without publishing a partial file. The pending state is recorded in the Run's
durable journal; no SQL transaction is held while the remote endpoint is called
or while the Agent later polls through another already-configured Tool endpoint.
Ready results use a stable Run/Tool/binding/operation identity, so a repeated
ready response recovers the same upload receipt. Changed bytes for the same
operation conflict rather than publishing a second result. Operation references
must be opaque identifiers, never bearer credentials. There is no generic poller
or callback listener: late responses after Run terminalization are rejected, and
each subsequent Tool call still passes current Workspace grants and endpoint
policy. A lost publication acknowledgement remains recoverable through the
existing upload idempotency record.
