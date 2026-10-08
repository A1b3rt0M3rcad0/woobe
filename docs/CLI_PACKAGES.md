# Portable Agent and Network packages

Package schema `1.0` describes a closed, portable author definition. It uses its
own API, operation worker and CLI commands; Manifest reconciliation remains a
separate contract. The implementation is reviewed in
[Woobe #179](https://github.com/A1b3rt0M3rcad0/woobe/pull/179) and
[woobe-cli](https://github.com/A1b3rt0M3rcad0/woobe-cli).

## Workflow

Create a Workspace Control Key in **Workspace settings → CLI Keys**, with the
Project grants needed to read or create the composition. Configure `woobe` with
the API origin and Project. A Runtime Key is separate and is needed only to run
the imported Agent or Network.

```powershell
woobe package export agent "Support Agent"
woobe package export agent AGENT_UUID --env staging
woobe package export agent AGENT_UUID --env release --version v1.0.20261007.01
woobe package export agent AGENT_UUID --env production
woobe package export network "Support Network" --env production
woobe package validate ./support-agent --locked
woobe package bindings ./support-agent --destination ./destination.yaml
# Fill destination placeholders before planning/importing.
woobe package plan ./support-agent --bindings ./destination.yaml --save-plan ./approved-plan.json
woobe package import --plan-file ./approved-plan.json --wait
woobe package status --checkpoint PATH_FROM_IMPORT_OUTPUT --wait
```

Export accepts an exact name or UUID. Names resolve in the selected project; duplicate
names require a terminal selection or explicit UUID. Draft is the default source.
Staging/production resolve current assignments; release selects the exact version.
The server freezes the source and its dependency bindings before artifact IO, without
falling back to another environment. Optional package name/version derive from the
captured definition. Unversioned sources use a deterministic portable-definition hash.
`--package-version` overrides metadata; `--version` selects a release with `--env release`.
Legacy `--source`/`--snapshot-id` requests remain supported.

Export writes readable YAML, multiline author instructions and an integrity lock.
`--destination` defaults to `./normalized-resource-name`; existing paths are never
replaced. `--output` controls terminal responses. JSON descriptors remain accepted;
plans, checkpoints and locks remain JSON. Edited files no longer match their old lock.
Managed pull/create/clone and compiled packages use block YAML with two-space
indentation and multiline instruction blocks. Explicit `.json` author descriptors
remain JSON. Formatting preserves numbers, nulls, empty collections and exact text;
CRLF and Unicode line separators use quoted escapes where YAML would normalize
them. Declared support files and downloaded export locks are never reformatted.

Import creates draft resources by default. Its checkpoint is automatically managed in
private CLI state, scoped to API/project/principal/input/lifecycle. Repeating the same
input reconciles the same operation, including after completion. An explicit new
`--checkpoint` opts into another import. Uncertain acceptance never authorizes replay.
Keep bindings/plans outside the portable directory. Packages without requirements
need no bindings. Focused command examples are available through `COMMAND --help`
and `woobe help package export agent --output compact`.


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
A legacy Draft without a complete ModelSpec snapshot is captured from the current
mutable Agent definition through the native owner compiler. Capture creates no
release and rewrites no saved snapshot. Complete native Drafts retain their version
identity for stage/test operations. Explicit snapshot IDs and Staging/Release/Production
selectors retain their exact captured definitions. Legacy native Model definitions are resolved through the existing
compatibility compiler and are not rewritten during export.

Portable Knowledge contains declared documents, parser/chunking configuration
and the embedding Model definition. The destination builds its own VectorSnapshot
and per-Agent KnowledgeVersion; vector bytes are not claimed to be identical.
`--knowledge binding` instead emits an external destination requirement and marks
the bundle as not self-contained. Missing or unfinished dependencies remain
observable waits and cannot produce final execution readiness.

MCP imports perform fresh destination discovery and apply permissions/bindings
by remote capability name. Each capability's `risk` preserves the native nullable
string label (1–256 characters), including `unknown` and custom classifications.
Risk labels do not change `review`, `deny` or `allow` permission modes.
The backend and CLI must use the same generated Package schema catalog.
OAuth configuration belongs to the destination;
credentials, OAuth sessions, cached discovered schemas and live execution state
are excluded. OAuth or readiness prerequisites can require an explicit resume.

Managed synchronization reuses an unchanged native MCP Tool without rediscovery.
Its approved revision is checked before reuse, and final Agent verification still
checks exact Tool snapshots and persisted MCP readiness. Rediscovery of an
unchanged Tool would increment its revision and invalidate saved Agent Drafts,
including Draft constituents of a Network. Edited Tools and new destination
imports continue to perform fresh discovery.

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
Apply. CLI credentials use private POSIX files or per-user Windows Credential
Manager. CLI Key login discovers Workspace/Project scope for each connection;
environment credentials remain optional for automation. See the CLI's
[Package guide](https://github.com/A1b3rt0M3rcad0/woobe-cli/blob/master/docs/PACKAGES.md).

## Migrations and qualification

Migrations `0078` and `0079` add Package operational persistence and complete
ProviderModel specification identity. `0079` permits distinct complete specs
for one credential/model. Downgrade refuses incompatible data instead of deleting
models to satisfy the former constraint.

Woobe draft PR #179 and the merged CLI development PRs carry the acceptance matrix and exact tested revisions.
Local integration tests use PostgreSQL, the real API/worker, native authorization,
a deterministic provider/MCP peer and a separate Runtime Key. Cross-project
export/import/re-export compares portable author fields and support files, then
executes after deleting local package directories. Native distribution tests
exercise the same complete shared fixture on Linux/macOS/Windows amd64/arm64.
The [acceptance matrix](testing/PACKAGE_ACCEPTANCE.md) maps T01–T26 to these
executable gates. Exact supported client/server build pairs and results are
published in the corresponding PR descriptions. Woobe PR #179 remains open in draft. Development improvements are delivered
in separate CLI PRs and merged only after their native distribution checks and
paired backend integration pass; backend approval and merge remain separate.

## Development compatibility diagnostics

Managed development requires the same Package catalog as the CLI. The server
normalizes CRLF to LF before hashing the catalog so a Windows checkout advertises
the same compatibility digest as Linux and macOS. A real schema change still
requires a matching CLI. Restart API processes after updating backend source.

The local `.woobe-config` can pin a connection independently of `context use`.
Pass `--context NAME` to explicitly select a different connection for a managed
command; private state remains scoped to that API, Workspace and Project.

An incomplete export diagnostic identifies the Agent primary/fallback Model or
Knowledge embedding Model path. Check the corresponding Provider credential and
Model binding; Project Environment diagnostics identify the missing field. A
historical snapshot without ModelSpec remains incomplete and cannot be silently
repaired from today's mutable configuration.
