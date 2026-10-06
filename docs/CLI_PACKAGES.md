# Portable Agent and Network packages

The Package feature is being implemented in the paired draft PRs Woobe #179 and
woobe-cli #10. It is separate from the existing Manifest reconciliation API.
The complete import/export acceptance suite has not passed yet.

The current API accepts bounded, explicitly declared `woobe-package` schema `1.0`
archives, persists their immutable inventory, and builds native destination plans.
Planning checks resource ownership, active credentials, complete ModelSpec
identity, native execution/Knowledge/RAG configuration, Skill packages and actual
Tool capability names, ready bound VectorSnapshots, and native Network limits.
It does not create Agents, invoke Models or execute Tools.

Authenticated endpoints are scoped to `/projects/{project_id}/packages`:

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/capabilities` | Exact schema catalog, native configuration schemas and supported operations |
| POST | `/uploads?locked=true` | Capture one bounded multipart archive and verify its inventory lock |
| GET | `/uploads/{upload_id}` | Read scoped upload identity and expiry |
| POST | `/plan` | Approve native effects, destination preconditions, lifecycle and audit fields |
| GET | `/operations/{operation_id}` | Read durable state and explicit readiness |
| POST | `/operations/lookup` | Reconcile an idempotency key in the request body |
| POST | `/operations/{operation_id}/cancel` | Fence further effects and retain committed resources |
| POST | `/operations/{operation_id}/resume` | Resume an observed dependency wait at its expected revision |

Capabilities intentionally do not advertise Apply or Export until the native
materializer and end-to-end qualification are complete. The Package operation
worker is registered, renews its lease during long phases, and automatically
rechecks waiting native dependencies with a bounded polling interval.
HTTP intake is bounded before JSON/multipart parsing, including chunked requests;
upload authorization runs before parsing multipart content.

Plans bind the API origin, Project, captured artifact, native capabilities,
binding identities/revisions and requested lifecycle. Public responses contain
protected references, never their resolved values or a hash of secret material.
Apply acceptance revalidates native destination preconditions. Each native effect
must commit its Package receipt in the same owner transaction. Recovery reuses
those receipts; a missing receipt cannot be treated as completion.

Current owner phase composition covers inactive Agent preparation and complete
Draft activation, complete Model resolution, immutable Skill version reuse,
create-only Project Environment and Secrets, document registration and vector
build readiness, and fresh MCP discovery with revision-checked commits. The live
CLI/API/PostgreSQL tests cover planning and native Agent/Skill/protected-binding
materialization. Network/lifecycle composition, full export, and the complete
checkpoint-driven CLI import remain under implementation; these tests do not
establish the complete Agent/Network roundtrip acceptance criterion.

`draft` is the default. Creating a Network must not incidentally activate any
standalone Agent in Production. Release/Production require explicit audit notes,
and Production also requires an activation reason. Readiness is an observed
native state, not a consequence of accepting an operation.

Migration `0079` changes ProviderModel uniqueness to include the complete native
ModelSpec hash. Distinct specifications for the same credential/model identity
can coexist. Its downgrade fails safely if those definitions cannot satisfy the
previous constraint; it does not discard Models to force a downgrade.
