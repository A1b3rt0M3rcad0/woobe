# Portable Agent and Network packages

Package schema `1.0` describes a closed, portable author definition. It uses its
own API, operation worker and CLI commands; Manifest reconciliation remains a
separate contract. The implementation is reviewed in draft PRs
[Woobe #179](https://github.com/A1b3rt0M3rcad0/woobe/pull/179) and
[woobe-cli #10](https://github.com/A1b3rt0M3rcad0/woobe-cli/pull/10).

## Workflow

Create a Workspace Control Key in **Workspace settings → CLI Keys**, with the
Project grants needed to read or create the composition. Configure `woobe` with
the API origin and Project. A Runtime Key is separate and is needed only to run
the imported Agent or Network.

```sh
woobe package validate ./support
woobe package plan ./support --project PROJECT_UUID \
  --bind credential.primary=CREDENTIAL_UUID --save-plan ./approved-plan.json
woobe package import --plan-file ./approved-plan.json --project PROJECT_UUID \
  --checkpoint ./import-checkpoint.json --wait --wait-timeout 5m
woobe package status --checkpoint ./import-checkpoint.json
woobe package resume --checkpoint ./import-checkpoint.json --revision REVISION
woobe package cancel --checkpoint ./import-checkpoint.json
woobe package export agent AGENT_UUID --source staging \
  --destination ./portable-support --name support --version 1.0.0
woobe package export network NETWORK_UUID --snapshot-id SNAPSHOT_UUID \
  --destination ./portable-network --name network --version 1.0.0
```

Validation and `--dry-run` are offline. Planning checks native configuration,
resource ownership, destination bindings, capabilities and required grants; it
creates no Agent or Network. Apply accepts exactly the approved plan and returns
a durable operation. `accepted` and `waiting_dependency` are not success.

`draft` is the default lifecycle. `staging` is explicit; immutable `release`
requires release notes. `production` requires release notes and an activation
reason. A Network freezes its constituent Agent snapshots without incidentally
activating standalone Agents in Production. Explicit node selectors preserve
Draft, Staging and Release identity independently of node labels.

## Portable composition

Agent packages preserve Behavior or legacy/versioned Prompt, Contract, complete
primary/fallback ModelSpec, generation parameters, native execution/context/
Knowledge/RAG policies, External Context, immutable Skills and resource files,
Tool author configuration, permissions and bindings. Native schema and readiness
validation is reused rather than introducing an alternate runtime. ModelSpec hints
reject unsupported fields and invalid limit/flag types rather than silently
discarding or coercing them. Embedded Model authentication is refused; destination
credentials supply authentication without changing a frozen specification hash.

Network packages include all selected Agent snapshots, stable portable node
keys, positions, capability descriptions, topology and settings. Export reads the
selected definition and its dependency closure in one consistent owner snapshot.
It does not fall back to mutable current configuration for historical snapshots.
A live Agent Draft without a saved snapshot can be captured without creating a
release. Legacy native Model definitions are resolved through the existing
compatibility compiler and are not rewritten during export.

Portable Knowledge contains declared documents, parser/chunking configuration
and the embedding Model definition. The destination builds its own VectorSnapshot
and per-Agent KnowledgeVersion; vector bytes are not claimed to be identical.
`--knowledge binding` instead emits an external destination requirement and marks
the bundle as not self-contained. Missing or unfinished dependencies remain
observable waits and cannot produce final execution readiness.

MCP imports perform fresh destination discovery and apply permissions/bindings
by remote capability name. OAuth configuration belongs to the destination;
credentials, OAuth sessions, cached discovered schemas and live execution state
are excluded. OAuth or readiness prerequisites can require an explicit resume.

## API and security

All paths below are relative to `/projects/{project_id}/packages` and require
native control-plane authorization.

| Method | Path | Result |
| --- | --- | --- |
| GET | `/capabilities` | Exact schema catalog and supported native operations |
| POST / GET | `/uploads` / `/uploads/{upload_id}` | Bounded archive capture / scoped inventory and expiry |
| POST | `/plan` | Immutable approved effects, preconditions, lifecycle and binding identities |
| POST | `/apply` | One asynchronous operation; mandatory bounded `Idempotency-Key` |
| GET | `/operations/{operation_id}` | State, revision, inventory, dependencies and readiness |
| POST | `/operations/lookup` | Reconciliation by the original idempotency key in the body |
| POST | `/operations/{operation_id}/resume` | Revision-checked continuation |
| POST | `/operations/{operation_id}/cancel` | Fence subsequent effects and retain committed resources |
| POST | `/export` | Captured definition and expiring scoped artifact receipt |
| GET | `/exports/{export_id}/artifact` | Bounded archive with transport and inventory integrity |

Uploads and export artifacts expire. An already accepted operation retains the
captured input needed for recovery. Its encrypted protected bindings, lease,
fencing token and phase receipts are operational records, separate from the
portable author bundle. Each receipt commits in the same transaction as its
native owner effect. Cancellation does not delete reused or committed resources.

Credentials and Secrets are destination bindings, never exported values. Public
plans mask protected aliases; private receipts and checkpoints contain no
resolved secret material. Apply resolves a protected alias once, records
request-in-flight durably before sending, and never automatically repeats an
uncertain mutation. A lookup miss requires reconciliation, not a second Apply.

Export verifies archive transport digest, exact file inventory and artifact
digest before publishing an entire destination with no replacement. Existing
destinations are refused. Symlinks, special files, hardlinks, escaping archive
paths, case collisions and resource-limit violations are rejected.

POSIX checkpoints use private files and native locks. Windows uses owner/DACL
checks and native locks in a private parent directory; directory replacement may
be blocked by the held Windows handle. Unsupported protection fails before
Apply. The legacy private-file credential store is POSIX-only; explicit environment
credentials remain available on Windows. See the CLI's
[Package guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/feat/portable-package-import-export/docs/PACKAGES.md).

## Migrations and qualification

Migrations `0078` and `0079` add Package operational persistence and complete
ProviderModel specification identity. `0079` permits distinct complete specs
for one credential/model. Downgrade refuses incompatible data instead of deleting
models to satisfy the former constraint.

The paired draft PRs carry the acceptance matrix and exact tested revisions.
Local integration tests use PostgreSQL, the real API/worker, native authorization,
a deterministic provider/MCP peer and a separate Runtime Key. Cross-project
export/import/re-export compares portable author fields and support files, then
executes after deleting local package directories. Native distribution tests
exercise the same complete shared fixture on Linux/macOS/Windows amd64/arm64.
The [acceptance matrix](testing/PACKAGE_ACCEPTANCE.md) maps T01–T26 to these
executable gates. Exact supported client/server build pairs and results are
published in the paired draft PR descriptions. Both PRs remain draft for review;
this implementation does not publish a release or merge either repository.
