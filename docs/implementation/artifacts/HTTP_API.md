# Direct Artifacts HTTP API v1

The API host imports only modules.artifacts.entrypoint. Routers translate bounded
transport DTOs and call the same authorized application facade as runtime users;
they open no SQL session and construct no repository. All routes require explicit
project_id (UUID) and environment query scope. Path/query artifact_workspace_id
names the independent Artifacts Workspace, never an Identity workspace_id. This
avoids changing the shared control-plane interpretation of existing Identity IDs.

| Family | Operations |
| --- | --- |
| /v1/artifact-workspaces | POST provision; GET filtered keyset page; GET /resolve by external identity |
| /v1/artifact-workspaces/{artifact_workspace_id} | GET metadata; PATCH CAS metadata/status |
| .../artifacts | GET immediate children; POST text file or directory |
| .../artifacts/{artifact_id} | GET metadata; PATCH CAS move/rename; DELETE CAS logical deletion |
| .../artifacts/{artifact_id}/content | PUT text revision with expected_revision |
| .../uploads | POST intent; GET /{upload_id}; PUT /{upload_id}/parts?offset=; POST /{upload_id}/finalize; DELETE /{upload_id} |
| /v1/artifacts/{artifact_id}/revisions/{revision_id} | GET exact immutable revision metadata; GET /content for download/Range |
| /v1/artifact-workspace-grants | POST scoped Workspace/namespace grant; DELETE /{grant_id}; administrative authority only |
| /v1/artifact-capabilities | GET implemented protocols and explicit limits; storage_readiness is not_probed |

Workspace provisioning retries are keyed by external_namespace/external_key and
the original request fingerprint. Other writes use operation_id; an optional
Idempotency-Key header must match it. Delete uses a required Idempotency-Key and
expected_version query. Metadata/path mutations require expected_version; a supplied
If-Match must be the matching quoted version. Text replacement requires the exact
expected_revision and path. Browser input cannot set origin, Run or Node lineage.
All body models reject unknown fields. Originals and representation IDs are separate
identities; no representation mutation route is exposed.

Control Keys use exact reviewed operation permissions and current project grants.
Runtime Keys additionally require the artifacts interface, current runtime:execute
scope, their bound Project/Environment and current Workspace/namespace grants.
Artifacts requests do not acquire Agent/Network execution permits or start Runs.
Administrative namespace grants let an external application provision its own
independent Workspaces. Shared human session/CSRF authority is retained. Unknown,
foreign or inaccessible Workspace/upload requests do not disclose catalog data.

Versioned request/response contracts and generated JSON schemas are in
contracts/artifacts/v1. OpenAPI includes Workspace, Artifact, revision, upload
status, paging, capabilities and error models. Public revision metadata excludes
storage keys, backend VersionId, credentials and signed URLs. Domain errors return
code/message/correlation_id/retryable in the version 1 envelope; HTTP authentication
uses ARTIFACT_ACCESS_DENIED with 401 and WWW-Authenticate: Bearer. Global server
body/connection-limit errors can retain the shared HTTP infrastructure envelope.

Proxy parts are bounded by min(request_max_bytes, runtime_max_request_bytes, 8 MiB),
not the whole-file quota. Default Runtime request size makes the default proxy part
limit 256 KiB; clients discover it rather than assume the adapter's larger ceiling.
The service allows at most 4096 parts and the configured upload_max_mb overall.
Inline bytes have a 256 KiB application ceiling; max_request_bytes also bounds the
entire encoded JSON request, including paths and escaping. Use resumable byte
upload when JSON encoding would exceed that request limit. Binary parts authorize
the current owner and write grant before consuming their bounded request stream.
The existing global server limits remain enforced.

Downloads are authorized proxy responses, private/no-store, with SHA-256 ETag,
X-Woobe-Source-Sha256, nosniff, safe attachment filenames and RFC 5987 UTF-8 names.
Single byte ranges include open-ended and suffix ranges; invalid/multiple ranges
return 416 and Content-Range: bytes */size. A mismatched If-Range serves the full
representation. Streams close even if response sending fails or the consumer
cancels. Full-file consumers should verify the supplied SHA-256; a range response
does not claim that its partial bytes hash to the whole original digest.
CORS explicitly allows Range/If-Range and exposes download/identity headers only
to configured origins. Logout and grant/key revocation block subsequent resolution;
an already authorized in-flight stream may finish. No pre-signed URL is issued or
stored. If a future S3 signed-download mode is introduced, a delivered URL remains
valid until expiry and cannot promise instantaneous revocation.

The real HTTP integration suite uses the complete FastAPI middleware/router stack,
real SQL authentication, PostgreSQL and both local and real S3-compatible adapters.
It covers provisioning, upload offsets/receipts, exact metadata, Range/UTF-8 names,
Control/Runtime scopes and interface restrictions, cursor tampering, configured
body limits, grant operations/CAS, browser password login/session logout (including
replay of the revoked token), CORS and revocation before download. Transport is
in-process ASGI; native API/Workers readiness and OpenAPI are checked separately.
No extraction, index or signed-URL readiness is advertised before implementation.

Stage 19 adds the exact-revision read-only representation and SourceRef routes,
verified downloads and new-Artifact editable copies described in
[REPRESENTATIONS.md](REPRESENTATIONS.md). Revision metadata includes optional
source_representation_set_id/source_representation_entry_id lineage. Internal
processing output keys and backend versions remain private.
