# Artifacts execution ledger

Source: [the supplied implementation plan](PLAN.md), preserved verbatim; its
SHA-256 and 60 ordered steps are recorded in [manifest.json](manifest.json).
Architecture decision: [ADR 0006](../../adr/0006-artifact-workspaces-document-runtime.md).
Baseline and ownership: [BASELINE.md](BASELINE.md).

Branch: `feat/artifact-workspaces-document-runtime`.
Base: `3dbcb3e1a7559f4a50ebca320e411933d46e8012`.

## Current state

Step 01 is complete. Baseline, ADR, ledger and CI guards are committed. The single
[PR #220](https://github.com/A1b3rt0M3rcad0/woobe/pull/220) is OPEN, Draft and has no
auto-merge. GitHub API connectivity recovered after the environment network draft
update; existing platform authentication worked without adding credentials.
PR #219 remains unrelated and untouched.

Step 02 is complete: exact pinned client snapshots, source/hash/license manifest,
local Go workspace and read-only client CI are included. Original client repositories
remain unchanged. CLI make check/build, both Go SDK modes, Python SDK 34 tests,
Ruff/build/Twine, source hashes and the new workflow validation passed. Step 03 is complete: domain identities/lifecycles, versioned DTOs, capability ports,
canonical schemas/fixtures and the Artifacts architecture policy are validated.
31 combined domain/contract/guard tests, Ruff and all nine architecture policies pass.
Persistence, authorization and adapters are not advertised as implemented. Step 04 is complete: additive PostgreSQL migration 0107, scoped catalog/revision
repositories and transactional Unit of Work passed 14 real PostgreSQL tests across
fresh and populated-upgrade paths. The native mocked regression passed 3135 tests
and 10 subtests. See PERSISTENCE.md.

Step 05 is complete: shared current-principal authority, explicit Artifacts Runtime
interface/actions, scoped live grants and restrictive Release/node intersection are
validated. 399 authority/Core/Artifacts regressions and 14 real PostgreSQL cases
passed. See AUTHORIZATION.md. Step 06 is complete: independent idempotent Workspace provisioning/resolution,
CAS metadata/lifecycle operations, scoped grants, signed SQL-filtered pagination
and public short-transaction composers are validated. 36 real PostgreSQL cases,
55 domain/guard tests and 3159 mocked regressions (plus 10 subtests) passed.
See WORKSPACES.md. Step 07 is complete: shared streaming object storage contract, local implementation
and Knowledge compatibility facade are validated with 9 targeted tests and 3165
mocked regressions (plus 10 subtests), with architecture checks passing.
See OBJECT_STORAGE.md. Step 08 is complete: atomic closed-handle promotion, immutable retry/metadata
reconciliation, cancellation-safe OS resources, staging cleanup and private scratch
passed 29 targeted/fault tests, including a deterministic reader/promotion race. A 64 MiB stream used under 8 MiB traced Python heap.
Full mocked regressions passed 3185 tests plus 10 subtests after the publication-lock
correction; 100 additional concurrent immutable-write pairs each had one winner
and one explicit conflict. Step 09 is complete: shared S3 streaming/conditional multipart, verified SHA-256,
ACK reconciliation, safe abort and Knowledge facade passed 40 targeted tests
(including 11 against a real pinned S3-compatible service), architecture, Ruff and
actionlint. The full mocked regression passed 3185 tests plus 10 subtests.
No real AWS qualification is claimed. Step 10 is complete: owner-scoped resumable proxy parts, quota reservations,
short database phases, immutable verified finalization, durable receipt/outbox and
concurrent abort/expiry/CAS reconciliation passed 89 integration/registry tests.
The existing security integration suite plus Artifacts authority passed 40 tests;
full mocked regression passed 3187 tests plus 10 subtests. See UPLOADS.md.
Step 11 is complete: idempotent bounded text publication, immutable provenance,
logical directories, atomic CAS rename/tree move/delete, historical directory
pages and editable copy identity passed 123 real integration cases. Full mocked
regression passed 3187 tests plus 10 subtests; 83 domain/storage/guard tests and
all architecture policies passed. See FILES.md. Step 12 is complete: direct Workspace/file/upload/download APIs, exact reviewed
Control permissions, Artifacts Runtime interface, scoped errors/response schemas,
proxy Range/CORS and live logout/grant/key revocation passed 147 integration tests.
Full mocked regression passed 3187 tests plus 10 subtests; native API/Workers are
reloaded and healthy. See HTTP_API.md. Step 13 is complete: immutable scoped recipes, passive component/library/model
readiness contracts, exact Workspace defaults/CAS and reproducible reuse identity
passed 155 integration cases, then 12 final profile/constraint cases; full mocked
regression passed 3198 tests plus 10 subtests. Store-only remains available and no
unimplemented parser/indexer is advertised. See PROCESSING_PROFILES.md.
Step 14 is complete: existing Worker process integration, standard durable outbox/
inbox delivery, fenced attempts/checkpoints/heartbeats, current authority checks,
reconciled cancellation/uncertainty, bounded admission/concurrency and fair
Project/Workspace selection passed 211 integration cases plus 12 final pipeline/
retry/factory cases. Actual process-death recovery passed on both adapters.
Full mocked regression passed 3198 tests plus 10 subtests. Store-only verification
is qualified; format adapters are delivered next. See PROCESSING_JOBS.md.
Step 15 is complete: deterministic native TXT/Markdown/JSON/CSV extraction, strict
encoding, original byte/Unicode/line provenance, structured untrusted data and
streamed private canonical checkpoints passed 117 unit/guard cases, 227 real
integration cases and 4 final ranged-read/ACK-recovery cases. Full mocked regression
passed 3219 tests plus 10 subtests before two additional passing unit cases. All
nine architecture policies passed. See NATIVE_TEXT.md. Step 16 is complete: resource-bounded isolated PDF extraction/rendering, physical
pages/printed labels, precise protected/invalid errors and explicit partial/OCR
coverage passed 139 targeted cases and 235 integration cases. The final renderer
dependencies also passed 8 repeated real PostgreSQL/storage PDF cases and 3229
mocked regressions plus 10 subtests. See NATIVE_PDF.md. Step 17 optional Docling
integration is next. Hugging Face model acquisition is currently refused by the
network proxy; a narrowly scoped network draft is saved and awaits environment
configuration activation. No weight-based profile is represented as qualified.
Step 17 is complete: official optional model-free Docling NativePdf/SimplePipeline
adapters, upstream hierarchy/table/figure evidence, version-fenced manifests,
resource/isolation controls and actual base-without-extra behavior passed 153
targeted cases, 243 real integration cases and 3245 mocked regressions plus 10
subtests. Controlled asset acquisition additionally verified 3 real pinned OCR
training files for next-step preparation; Docling native needs no model weights.
See DOCLING.md. Step 18 is complete: native image/PDF visuals, pinned real Tesseract/Portuguese
models, selective page/image-region OCR, raw confidence/orientation provenance,
portable integrity receipts, bounded streaming assets and real descendant cleanup
passed 166 targeted cases, 263 integration cases and 3258 mocked regressions plus
10 subtests. Original bytes, durable recovery and cancellation were verified on
both storage adapters. See OCR.md. Step 19 is complete: immutable coherent representation bundles,
source maps, bounded verified Unicode reads, read-only Range downloads and
new-Artifact editable-copy lineage are published through current authority. Ready
state, head CAS, event and job success commit atomically; sealed recovery and
quota intents keep failed/orphan outputs invisible and charged. 218 targeted cases,
299 real integration cases and 3258 mocked regressions plus 10 subtests passed;
late source/result/copy integrity checks and actual Docling figures also passed.
Four additional real Docling cases verify 210-block/105-parent hierarchies across
metadata batch commits on both adapters and migration paths.
See REPRESENTATIONS.md. Step 20 is complete: deterministic native structural trees,
explicit heading/canonical/page/block fallback, immutable versioned graph manifests,
signed child pages and bounded index-aware source reads passed 229 targeted cases,
332 real integration cases and 3275 mocked regressions plus 10 subtests. Generation,
index and job success share one fenced transaction; recovery, exact historical
sources and real large Docling hierarchies were verified. See INDEXES.md. Step 21
governed model enrichment is implemented and its deterministic provider, durable
calls, authorization, metering and recovery tests passed. Per the user's requested
scope adjustment, a live provider call is optional deployment qualification and
does not gate implementation completion. No OpenAI account, key, model or endpoint
is required. Provider-specific functionality remains unavailable until an
Environment owner configures an approved provider through the existing approval
path; no live-provider result is claimed. See PLAN_ADJUSTMENTS.md.

The stage commit carries `Plan-Step: 01/60`; a file never records its own containing
commit SHA. CI reconciles commit subjects/trailers against the execution manifest.
No final acceptance is claimed. Runtime capabilities are exposed only when their
authorization, service and adapter steps are implemented and validated.

## Validation and resumption

Local step 01 validation passed: 14 guard tests, Ruff for both new Python files,
117 combined quality-gate/architecture tests, and all eight governed module
architecture checks with zero violations. Commands and observed results are
recorded in the manifest; the initial API connectivity failure was resolved and PR creation/status verified.

Use the baseline commands and outcomes in BASELINE.md. Run the new guard tests
with `.venv/bin/python -m pytest -q tests/architecture/test_artifacts_plan_guard.py`.
Validate the ordered committed series with
`python3 scripts/validate_artifacts_plan.py --base 3dbcb3e1a7559f4a50ebca320e411933d46e8012`.
CI supplies its real PR event file and refuses non-Draft execution. Final audit
additionally supplies `--final` and requires exactly 60 completed, evidenced steps.

Never create empty commits or mark steps complete with placeholders. Correct a
step before committing it; later corrections require a controlled reconciliation
of its responsible commit. No merges, automatic mirrors, tags, production changes,
release/publication or Ready-for-review transition are part of this delivery.

## Step 21 completed with provider-neutral acceptance

Governed model binding, durable bounded model calls, strict source-scoped response
validation, inferred summary publication, uncertain outcome recovery and idempotent
Metering integration passed deterministic provider-contract and PostgreSQL/local/
S3 integration tests. The explicit execution-scope adjustment in
PLAN_ADJUSTMENTS.md makes live-provider calls optional deployment qualification;
the original live-provider check remains `not_run` and is not claimed as passed.
No OpenAI binding is required.

## Steps 21–26 completed

Step 21 is accepted under the user-requested provider-neutral scope in
[PLAN_ADJUSTMENTS.md](PLAN_ADJUSTMENTS.md). Deterministic provider-contract and
PostgreSQL/local/S3 tests passed; the opt-in live provider call remains `not_run`
and is not a prerequisite. No OpenAI account or key is required.

Step 22's pinned local PageIndex adapter and explicit structural fallback passed
14 unit and 8 PostgreSQL/local/S3 tests. Optional startup, packaging, license and
worker-isolation checks passed. See [PAGEINDEX.md](PAGEINDEX.md).

Step 23's bounded, scoped PostgreSQL text search passed 8 fresh/populated
PostgreSQL cases across local/S3, including revocation, cursor tampering and GIN
query plans; 180 unit cases passed. See [SEARCH.md](SEARCH.md).

Step 24's bounded navigation, exact source resolution, page labels/images and
runtime authorization passed 32 PostgreSQL/local/S3 cases and 352 Artifact/security
unit tests. See [REPRESENTATIONS.md](REPRESENTATIONS.md).

Step 25 versions Artifact capabilities in Agent/Network package 2.0. Existing
Agents remain disabled, binding uses a hidden External Context key plus logical
namespace, and Package 1.0 remains unchanged. Core roundtrip tests, CLI package
schema checks, the full CLI check, Ruff and architecture checks passed.

Step 26 resolves and authorizes Workspaces by logical namespace/key in the
current Project and Environment before provider execution. It freezes the observed
catalog version, rechecks every capability action against current grants, stores
the private binding on the Session, and rejects Workspace changes for stateful
Sessions with history. 37 focused unit cases and 2 real PostgreSQL fresh/populated
cases passed; Alembic head is 0118 and all architecture policies pass.

## Step 27 completed

Network Artifact Workspaces now resolve once at run acceptance from a hidden, required
External Context key. The private binding and non-secret authenticated-principal
snapshot survive Session continuity, child invocations, retries, reattachment and
reruns. Node actions are constrained by the Network ceiling and intersected with
the frozen Agent capability; Nodes without actions receive no Artifact binding.
Public callers cannot spoof the worker-only Network metadata.

Focused Network, Agent and Package tests passed (197 cases), including the action
intersection, disabled-root denial, Workspace-switch conflict and rerun identity.
Four fresh/populated PostgreSQL cases passed for migration 0119 and binding
roundtrips. CLI checks, generated schemas, Ruff, all architecture policies and
`git diff --check` passed. See [NETWORK.md](NETWORK.md).

## Step 28 completed

Run requests now use the catalog version frozen at Acceptance for listing, search,
and exact reads. Session-scoped bindings retain their first accepted catalog view;
run-scoped bindings resolve a fresh version at each Acceptance. Every operation
still checks current grants. Signed page cursors preserve their catalog snapshot,
and exact retained revisions remain available after later updates, renames, or
deletion only when the Run's snapshot contained them. Reads never fall forward to
the current head.

Successful Run source reads and search results returned to a Run are recorded as
exact `SourceRef`s in a deduplicated per-Run manifest. The manifest is fixed to one
catalog version and scales with sources consumed. Explicit Run-output reads require
the exact revision receipt and a matching Run ID; Node outputs also require a
trusted allowed-Node identity. No catalog copy or provider credential is needed.

The Artifact, Agent and Network unit suite passed 191 tests (9 skipped). Combined
fresh/populated PostgreSQL file and source-manifest tests passed 24 cases (20
skipped); the focused manifest roundtrip passed 6 (2 skipped) with locator/hash
provenance. Ruff, all nine architecture policies, migration head 0120 and
`git diff --check` passed. See [RUNTIME.md](RUNTIME.md).

## Step 29 completed

Agent and Network accept ordered typed text and exact Artifact revision references,
while the existing `message`/`content` fields remain their text projection. The
public DTOs reject ambiguous dual input and bound part count, text size, reference
count and media-type hints. The shared contract keeps Agent independent from the
Artifacts bounded context.

Validated references are rechecked against current `read` grants and the accepted
Workspace catalog before model invocation. Agent messages and recovered history,
accepted execution snapshots, Network messages/execution rows, Network reruns and
assistant result metadata retain the exact identifiers without file bytes, base64
or signed URLs. Network idempotency keys are bound to both text and typed parts.
The language runtime records authorized image references but fails safely before
provider invocation. Step 30 adds bounded internal Artifact Tools for document
references; image input remains gated until the visual stage. No provider-
specific key or OpenAI binding is required by the Artifact Tools.

The focused Artifact/Network/Agent unit suite passed 388 tests (9 skipped). Fresh
and populated disposable PostgreSQL migration/binding tests plus Network rerun
roundtrip passed 5 tests. Ruff, all nine architecture policies, Alembic head 0121
and `git diff --check` passed. See [RUNTIME.md](RUNTIME.md).

## Step 30 completed

Artifact-enabled Agents receive a stable internal Tool inventory constrained by
the effective read/search/write/process actions. List, inspect, search, outline
and source reads are bound to the accepted Workspace and catalog snapshot;
write and process requests use deterministic per-Run operation IDs. Tool
arguments contain no Workspace or catalog selector. Document content is only
read through bounded source references, and process returns a job ID/status
without polling. Image references remain gated for the later vision stage.

The deterministic model test called search, source read and write through the
existing Agent Tool loop. Repeated writes reused the same deterministic operation
identity for the existing upload receipt path; scope tampering and unexposed Tool
names were denied; processing errors remained failed Tool calls. See
[RUNTIME.md](RUNTIME.md).

## Step 31 completed

Artifact exploration is capped at 24 internal Tool calls and 64 KiB of UTF-8
source text per Run. Reads are clamped before the Artifact service call, exact
repeated SourceRef/offset reads are cached, and continuation/truncation/coverage
fields remain visible. Artifact Tool results are marked as untrusted document
data when entering model context and retain that trust metadata through compaction
and recovery. No exact token count is fabricated for unknown multimodal usage.

The focused budget, deduplication and trust tests passed with context assembly,
checkpoint recovery and runtime Tool regressions; Ruff and architecture checks
passed. See [RUNTIME.md](RUNTIME.md).

## Step 32 completed

Artifact writes now return versioned output references in synchronous Agent and
Network results, assistant message data, terminal Run records and reattached
`run.state`. The existing durable upload receipt is committed before
`artifact.available`; deterministic Run operation IDs allow retry to recover the
same revision if event recording is interrupted. Live and journal replay
projections expose only allow-listed metadata, and duplicate availability events
upsert by exact Artifact revision without re-running work.

The focused Agent/Network output and journal projection suite passed 37 tests,
including repeat-event stability, exact source/output references and removal of
blob/credential fields from public events. Ruff, architecture policies and
`git diff --check` were run for the changed modules. No external model credential
or live provider call is required for this provider-neutral persistence stage.
See [RUNTIME.md](RUNTIME.md).

## Step 33 completed

Configured HTTP Tool inputs can bind exact Artifact revisions using streamed
`bytes` or `multipart` bodies, or a short-lived S3 download URL placed only in a
configured HTTPS request body. Runtime resolution checks the accepted Run's
`transfer` and current `read` permissions, exact catalog/revision, content type,
size and SHA-256. Existing destination DNS/egress policy and no-redirect
behavior remain in force. Signed URLs are limited to 60 seconds, require a
public HTTPS S3 endpoint and are removed from returned Tool results.

The Tool records durable `artifact.transfer.*` journal facts with deterministic
operation ID, exact inputs, hashes, destination host and outcome; no body bytes,
secrets or signed URLs enter those events. Configured idempotency headers receive
the operation ID, while an unacknowledged transfer is marked uncertain and is
never retried automatically. 90 focused Artifact/HTTP/transport/journal tests
passed, plus Ruff and all nine architecture policies; `git diff --check` passed.
See [RUNTIME.md](RUNTIME.md).

## Step 34 completed

MCP Artifact bindings now negotiate only against the frozen schema for one
selected remote Tool. Before each file call, the runtime rechecks `tools/list`
through the same MCP URL and current session; a missing or changed schema fails
before source materialization. The model sees an exact Artifact reference, while
the peer receives only bounded base64 bytes (up to 4 MiB) or an authorized,
public HTTPS URL expiring within 60 seconds. Paths and internal storage URIs are
never treated as remote file contents.

MCP transfer results use the durable Artifact transfer receipt, redact temporary
URLs and preserve uncertainty without retrying. `isError` stays failed.
`resource_link` is read through the configured peer only; up to four resources
and 64 KiB text per resource are exposed. External filesystem URIs and binary or
oversized resource bodies are omitted. Text-only MCP Tools retain their original
arguments and behavior. Package 2.0 includes the binding schema while Package
1.0's catalog remains byte-for-byte unchanged.

The MCP transport, runtime, compatibility, and Package 2.0 selection passed 29
focused tests, including a full `HttpToolExecutor` exchange with an in-process
MCP peer, schema drift, URL redaction, resource limits, `isError`, and per-Run
session-cache isolation. Package schema generation/check, Ruff, all nine
architecture policies, and `git diff --check` passed. The Go CLI package-format
test was skipped because this environment's `/usr/bin/go` is not the Go
toolchain (`go test` returns `Go: Unknown option: test`).

## Step 35 completed

HTTP and MCP output bindings now validate MIME, byte limits, optional SHA-256,
application success, and exact remote operation references before publication.
The new Artifact revision records producer Tool, originating Run, external
operation reference, and exact input SourceRefs. A response-body capture stays
bounded and temporary; JSON base64 and MCP resource bytes are removed from the
model-facing result once the durable receipt exists.

Configured asynchronous HTTP responses may declare a status pointer, pending
statuses, and operation reference. A pending result is journaled durably without
opening SQL or publishing partial bytes. A later call through the already
configured Tool endpoint may poll it; repeated ready responses recover one
stable upload receipt, and changed bytes conflict. No generic poller/callback
listener exists. Output after Run terminalization is rejected, while the upload
authorization path rechecks current grants before publication.

The output, HTTP/MCP transfer, cancellation, scope and journal unit suite passed
36 tests, including rejection of partial JSON payloads and URL strings without
ever fetching them. PostgreSQL fresh/populated upload integration passed 22 cases across
local storage; 22 S3 parameter cases were skipped because this environment has no
S3 integration config. The new migration 0122 was exercised on both PostgreSQL
paths. Ruff, Package schema generation/check, Package 1.0 byte equality, CLI
embedded Package 2.0 comparison, all nine architecture policies, and
`git diff --check` passed. No live model/provider credential was used or required.
Provider live qualification for later vision/image stages is optional under
[PLAN_ADJUSTMENTS.md](PLAN_ADJUSTMENTS.md). See [RUNTIME.md](RUNTIME.md).

## Step 36 completed

Agent visual input now resolves only exact PNG/JPEG/WebP Artifact revisions after
current read authorization, catalog checks, ModelSpec image capability, and an
explicit provider adapter formatter all pass. A provider or fallback model that
does not advertise image input is rejected before the storage read. Each image
is limited to 4 MiB, each Run to four images and 8 MiB total, with a lower
effective model `max_input_bytes` applied before bytes are read.

The scoped reader verifies revision size, SHA-256, media type, and image
signature, then records the exact consumed SourceRef. Bytes/base64 exist only in
the model invocation boundary. Logs show text blocks only; persisted messages,
snapshots, and public events continue to carry exact references without image
bytes. OpenAI-compatible and Anthropic formatters have peer contract tests; no
live model call or OpenAI credential was needed.

The visual input, file-service storage, provider capability, model runtime and
Artifact acceptance suite passed 61 tests; Ruff, all nine architecture policies, and
`git diff --check` passed. See [RUNTIME.md](RUNTIME.md).

## Step 37 completed

The internal image-generation Tool now invokes the one-shot `image.generate`
strategy only for an explicitly declared compatible ModelSpec and an accepted
Workspace with `write` permission. Provider discovery preserves explicit image
operation/modalities and generation constraints. The Tool schema limits sizes
and image count from that spec, and a per-Run budget allows at most four generated
images.

Provider responses are bounded and validated as complete PNG/JPEG/WebP images,
including decoded dimensions, before quota-enforced Artifact publication. Each
revision carries its producer Tool, Run, provider request reference, hash and
exact source revisions used by the Run. The durable journal records pending,
completed and uncertain states. Deterministic provider idempotency keys and
per-image upload IDs support lost-ack recovery without blindly repeating paid
generation. Cost and usage are kept only when the provider reports them.

The deterministic provider/persistence suite passed 60 tests across adapter,
capability discovery, size/count/response bounds, credential scoping, image
validation, multiple-output persistence, exact lineage, replay and uncertainty.
The PostgreSQL/local upload integration passed 22 tests; 22 S3 cases were skipped
because the environment has no S3 configuration. Ruff, all nine architecture
policies, generated package schema checks and `git diff --check` passed. The
optional live provider smoke remains skipped under
[PLAN_ADJUSTMENTS.md](PLAN_ADJUSTMENTS.md); no OpenAI binding or live-provider
result is claimed. See [RUNTIME.md](RUNTIME.md).

## Step 38 completed

Knowledge selection now explicitly supports `none` while the omitted field
continues to mean historical `rag`. The no-op strategy performs no retrieval,
and runtime preparation skips stale vector/version bindings before opening their
repositories. Artifact Tools remain available independently and continue to
enforce their own Workspace and operation policies. Portable Agent authoring
rejects conflicting strategy declarations; Package 2.0 can preserve `none`
without exporting an unused Knowledge/vector snapshot, while Package 1.0's
schema and generated catalog remain byte-for-byte unchanged.

The Agent, Release compatibility, portable definition/materialization,
Artifact Tool, and Package regression suites passed 148 tests. Ruff passed on
the touched strategy, authoring, runtime-preparation, and test modules. All nine
architecture policies, generated schema checks, Package 1.0 byte parity, CLI
embedded Package 2.0 catalog/digest parity, and `git diff --check` passed.
No migration or live provider was required. See [RUNTIME.md](RUNTIME.md).

## Step 39 completed

Added the versioned `artifact-document-exploration` Skill package under
[`docs/skills/artifact-document-exploration/`](../../skills/artifact-document-exploration/SKILL.md).
It guides a bounded locate→inspect→outline→read→compare→answer workflow,
requires exact SourceRef citations for claims, and reports absent topics, partial
coverage, unreadable tables and missing OCR without fabricating evidence. The
package declares only the real list/inspect/outline/read/search Artifact Tools
as required; persistent writing stays optional and requires its separate bound
Tool and write permission. Document contents remain untrusted data. Publishing
and installing a fixed version uses the existing Project Skills catalog and
does not grant permissions or alter a Release.

The new package parser/runtime tests and the existing Skill activation,
version-pin, Release and Network Skill regression suites passed 43 tests.
They verify package/resource validity, exact required Tool names, activation
failure when a Tool is missing, and that the reference loads only after
activation. Ruff and `git diff --check` passed. No migration, external
installation or live provider was needed. See [Skills](../../skills/README.md).

## Step 40 completed

The Go SDK now exposes a direct Artifacts client fixed to one Project,
Environment and explicitly supplied Runtime Key. It covers Workspace
provisioning/list/resolve/update, paginated files and CAS mutations, exact
revision metadata and streamed Range downloads, resumable upload intent/status/
bounded parts/finalization, processing profiles and jobs, search, structural
indexes/nodes, and exact SourceRef reads. It does not create a Session or Run,
accept a Control Key fallback, fetch document URLs, follow Artifact redirects,
or transparently retry mutations. A streaming upload validates the caller's
declared byte count and SHA-256 before finalization and returns the upload ID
when an outcome needs explicit status reconciliation. An end-to-end Go example
creates a Workspace, streams a PDF, and requests durable processing.

The SDK and example passed `gofmt`, `go test -race` in both `GOWORK=off` and the
monorepo workspace, and `go vet` in both modes. HTTP contract tests cover fixed
scope and Runtime Key placement, bounded upload parts, idempotency, checksum
mismatch/abort, redirect refusal, Range downloads, SourceRef citations, tree
pagination, and exact-revision ProcessingJobs. The CLI consumer's entire Go test
suite also passed against the local SDK via `go.work`. See the Go SDK README.

## Step 41 completed

The Go Runtime client accepts bounded text/Artifact content parts for both Agent
streams and synchronous Network Runs, preserves External Context exactly, and
validates immutable output/source receipts. Typed `artifact.available` and
transfer receipts do not fetch bytes; image-only terminal results are supported.
The shared protocol-v2 fixture covers both request surfaces and output/source
receipts. Its SDK-local embedded copy is byte-checked against the monorepo fixture
while remaining usable when the SDK is built standalone. `run.state` replacement
restores terminal Artifact metadata after reattach without a second POST.

Go 1.27.1 formatting, standalone and workspace `go test -race`, workspace
`go vet`, and the complete CLI Go suite passed. The CLI suite caught and drove a
fix for JSON number precision in typed synchronous results. See the Go SDK README.

## Step 42 completed

The Python SDK now mirrors the Go client with explicit Project/Environment/
Runtime Key-scoped Workspace operations; paginated Artifact revisions; bounded
resumable uploads with ACK uncertainty receipts; exact-revision streamed
Range downloads; processing profiles/jobs; search, source reads and document
indexes. Agent/Network Chat accepts bounded `content_parts`, Network/Agent
synchronous `run(...)` returns typed Artifact/SourceRef receipts, and Runtime v2
events expose typed Artifact and transfer metadata without fetching bytes.
External Context remains unchanged and create-only. Mutation outcomes are never
silently retried; cancellation and integrity failures attempt staging cleanup.
The Python tests compare the same runtime fixture with both the canonical
monorepo and Go SDK copies, and retain a standalone fallback.

Ruff passed and 43 tests passed in the monorepo plus 43 from an isolated source
copy. Local wheel/sdist builds and Twine checks passed under `/tmp`; no package
was published or version changed. See the Python SDK README and
[`RUNTIME_STREAMING.md`](../../../clients/woobe-sdk-python/docs/RUNTIME_STREAMING.md).

## Step 43 completed

The CLI now operates Artifact Workspaces through the local Go SDK and a direct,
explicit Project/Environment Runtime Key scope. It supports Workspace create,
list, resolve, inspect and CAS update; Artifact listing/inspection, exact
revision metadata, search, SourceRef and document-node reads, processing,
move/delete, upload/resume and exact-revision download. Discovery documents the
Runtime grant boundary and the concrete HTTP routes without treating them as
administrative Control operations.

Uploads stream bounded parts, save a private checkpoint before the begin
request, reconcile uncertain begin/part/finalize outcomes with the original
operation ID, and revalidate source bytes before finalization. Replacements
require exact revision CAS and `--yes`. Downloads verify byte count and SHA-256
before atomic publication; they do not print binary content, and an output
created concurrently is protected unless replacement was explicitly confirmed.
Search SourceRefs are accepted as strict bounded JSON for exact source reads.

The Go 1.27.1 CLI suite passed `go vet ./...` and `go test -race ./...` across
all packages. `gofmt`, module verification, the generated command catalog and
all 118 offline skill command examples passed. Nine Node installer tests and
64 Python script tests passed; the historical CLI completeness ledger remains
66 done, 34 partial and one pending. Packaging verification passed for all six
archives, with native Linux amd64, npm and skill smoke on an isolated temporary
snapshot. No release or publication occurred; that local smoke is not six-host
qualification. No live provider call or OpenAI API key was used. See the
[Artifact Workspaces CLI guide](../../../clients/woobe-cli/docs/ARTIFACT_WORKSPACES.md).

## Step 44 completed

Runtime YAML retains legacy `input` and now accepts ordered `content_parts`
with exact Artifact/revision references. It rejects unknown spellings, duplicate
JSON fields, extra or contradictory part fields, mixed text/content input and
invalid references before a request. Agent `/v1/run` and Network `/v1/run`
forwarded the same multipart contract and session-scoped External Context in
HTTP fixtures. A backend without multimodal support returns its explicit error;
the CLI does not flatten Artifact references into text. Local `schema`,
`validate-input` and `--dry-run` describe/validate the protocol without claiming
server authorization or contacting a backend.

Package 2.0 authoring documents logical External Context Workspace bindings,
actions/limits and pinned processing profile revisions. Agent and Network YAML
exports round-trip with stable values and exclude private Workspace IDs, signed
URLs, secrets and binary source assets. Legacy Package 1.0 schema bytes remain
unchanged, and destination access continues to require runtime resolution and
authorization. The CLI guide and embedded coding-assistant skill now document
upload, source references, optional PageIndex and the distinction between that
assistant skill and a Woobe runtime document Skill.

Go vet and the complete CLI race suite passed; final focused race tests passed
after the last Runtime change. Forty-five package/runtime acceptance tests, nine
Node installer tests, 64 CLI script tests and 120 offline skill command examples
passed. All six local archives and Linux amd64, npm and skill smoke checks passed
on disposable snapshot `a4ad49481bac77e6e4b2eeb7bd4de22bc4b29842`; this does not
qualify the other five hosts. No runtime provider request, OpenAI API key,
release or publication was used. See the
[Package Workspaces and multimodal Runtime guides](../../../clients/woobe-cli/docs/PACKAGES.md)
and [Runtime examples](../../../clients/woobe-cli/docs/USAGE.md).

## Step 45 completed

The shared browser Runtime client now validates protocol-v2 ContentParts,
exact Artifact revision references, SourceRefs and immutable output receipts.
It decodes `artifact.available`, terminal Artifact outputs, transfer metadata,
processing-job status and opaque cursor pages without performing network I/O.
Additive public receipt and locator fields are retained. Semantic observers pin
Run, Session and Run kind identity; a `run.state` snapshot is consumed as a full
replacement so removed sources do not remain in a stale projection. Web,
Network and Embed use the same replacement helper while legacy text output stays
compatible.

The canonical Artifact fixture remained byte-identical to both Go and Python
SDK copies and was decoded through the shared client for Agent, Network,
availability, completed and image-only cases. Web passed all 684 tests and its
production build. Embed passed all 29 tests, typecheck and production build.
The standalone runtime-client typecheck and five architecture-boundary tests
passed. These checks are local protocol coverage; no provider key or live Run
was used.

## Steps 46–50 completed

The Workspace Explorer, document tree/source reader, Agent and Network bindings,
Playground Artifact content, and Network execution tree are present. The final
Web run passed 705 tests with local API/ChatSurface URLs configured; the
production TypeScript/Vite build passed. The generated Web bundle still emits
Vite's large-chunk advisory, recorded as a build warning rather than a failed
build.

## Step 51 completed

ChatSurface/Embed now renders exact-revision Artifact inputs and authorized
output download cards while keeping metadata observation separate from byte
fetching. Embed passed 32 tests, typecheck and production build. Python SDK
passed 43 tests and the Go SDK suite passed on Go 1.27.1. No provider key was
used.

## Step 52 completed

Artifact operation metrics use bounded operation/outcome/direction labels and
keep byte transfer totals separate from durations. Redaction, uncertainty,
external output and failure handling passed the focused 51-test selection.

## Step 53 completed

The default light stack and explicit document/PageIndex profiles both pass
Compose configuration validation. Capability probes distinguish installed
processors from process health, and the optional-profile tests confirm that
store-only operation does not import parser/model extras.

## Step 54 completed

Fresh and populated PostgreSQL migration paths pass through `head`, and the
HTTP compatibility suite succeeds after the lifecycle schema changes. The
upgrade/rollback runbook disables features by application code and keeps the
schema/tombstone ledger; it documents that downgrade is not a rollback path.

## Step 55 completed

The database-backed run covered direct HTTP workspace/file operations, Runtime
binding, pinned Run sources, search and deterministic model-provider ports. A
new two-user case resolves three Workspaces in one Project, switches the first
user between two journeys, and rejects each cross-user read. The selected
integration run passed 53 tests; 34 S3 cases were skipped because no isolated
S3 endpoint was configured.

## Step 56 completed with restore limits recorded

Retention, deletion fencing, resumable cleanup, quota release and exact-object
purge pass on PostgreSQL/local storage. The export route streams a pinned
NDJSON manifest with a final digest/count; restore reconciliation fences any
Workspace found in the newer authoritative tombstone ledger. Thirty lifecycle
and upload integration cases passed and 22 S3 cases were skipped. A coordinated
full database/object snapshot restore was not run; the isolated-target procedure
and this limit are documented in `BACKUP_RESTORE.md`.

## Step 57 completed with scale limits recorded

The synthetic PostgreSQL run loaded 10,000 Workspaces, 100,000 Artifacts and
1,000,000 source blocks. List p95 was 3.289 ms (500 ms budget), search p95 was
12.094 ms (1,500 ms budget), and 50 concurrent Workspace lists completed in
594.505 ms. The JSON includes query plans and visible resources. Lifecycle/job
tests cover worker death, bounded retries and storage failure. Broker/Redis
outage and production byte-throughput qualification remain outside this
metadata rehearsal; see `SCALE_BENCHMARK.md`.

## Step 58 completed under the provider-neutral adjustment

A deterministic fixture freezes 36 synthetic document records, 80 queries,
20 generation tasks, source hashes/locators and a predeclared contract rubric.
Tests validate exact authorized source references, unanswerable-query abstention
shape and generated-task source membership. Existing PostgreSQL search and
provider-port tests passed. This does not claim semantic model quality, OCR
quality or live-provider qualification; no OpenAI key/account/endpoint was
required or read.

## Step 59 completed

The documentation index and end-to-end developer guide link the API, SDKs,
CLI, Runtime, deployment, compatibility, observability, retention and recovery
procedures. Local Markdown targets resolved; generated Artifact schemas matched
source contracts; scoped Ruff and whitespace checks passed.

## Step 60 completed

The branch now contains the complete 60-step linear commit series. Each commit
has the planned subject and `Plan-Step: NN/60` trailer, and none is a merge or
empty commit. The final audit also updates the guard allowlist for the two exact
optional Compose profile files. The plan validator passes against the immutable
base and confirms all 60 steps are complete while the PR remains Draft.

PR #220 remains OPEN and Draft with auto-merge disabled and `master` as its
base. Test-repair updates are folded into step 60 so the branch retains its
exact 60-commit plan series. The
implementation does not require an OpenAI key, account, endpoint, or model.
Steps 21 and 58 use provider-neutral contracts and deterministic fixtures;
there is no live-provider or semantic-generation qualification claim.

The operational boundaries recorded above remain part of the acceptance:
S3-only cases were skipped without an isolated S3 endpoint; a coordinated full
database/object snapshot restore and production-scale byte-throughput rehearsal
were not run; the scale run covers synthetic PostgreSQL metadata; and the
retrieval evaluation checks deterministic contracts rather than model quality.

The acceptance repair follow-up fixed the sole failure found in the complete
backend integration run: the network rerun fixture now supplies a valid
provider-neutral draft configuration snapshot. The full run had 686 passed
and 216 skipped; after the fixture correction, its previously failing test
passed in isolation. Acceptance (132 passed), storage (450 passed, 24 skipped),
OCR (32 passed), and frontend (705 passed plus build) also pass locally. GitHub
qualification passed on the updated Draft candidate: Acceptance, frontend,
Package Build, CLA, Quality Gate, Container quality, and Backend test suite
completed successfully in GitHub Actions.

The prior CI head exposed several qualification failures. Their fixes were
validated locally and in the final GitHub reruns. The
representation-page composer now uses the configured transactional handler;
Agent outbox claims delegate to the repository and recover stale publishing
locks; sanitized PDF and worker subprocesses receive the package source root;
and API/worker images install a patched Pillow version for profiles without the
Docling compatibility constraint. Legacy Agent tests now assert the current
module boundaries and worker behavior instead of obsolete source layout.

The backend mocked suite passes with 3,456 tests and 9 optional skips after
adding the published skill package to its test image. The Agent suite passes
with 693 tests, the quality gate with 88 tests, and the
architecture checker reports zero violations across nine modules. The full
storage+S3 qualification passes with 450 tests and 24 optional skips while the
ambient PYTHONPATH is unset. Native OCR qualification passes with the pinned
Tesseract models; frontend browser qualification passes in CI. The local Docker
image build and Trivy scan could not run in this workspace because it lacks
sufficient free disk and a local Trivy binary; final GitHub container
qualification passed.

The final backend CI rebuild caught an image-context issue that the local
pytest run could not detect: the root `.dockerignore` excluded the published
artifact skill even though the mocked test image copied it. The ignore rules
now re-include only `docs/skills/artifact-document-exploration`; a BuildKit
scratch-context copy verifies the file is present, and the backend workflow
completed successfully as run 39670199830. Container quality passed on the same
commit as run 39670199908, including vulnerability scans and multi-architecture
builds.

The separate manual Security audit run scanned all reachable repository
history and reported 24 historical matches in older configuration, test and
example files. The PR-scoped Security audit had passed on the previous PR head;
no broad Gitleaks ignore was added to suppress the repository-wide findings.
