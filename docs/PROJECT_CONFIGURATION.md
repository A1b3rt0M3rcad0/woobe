# Project configuration

Implementation status: the central store, typed references, runtime resolution,
configuration UI and CLI commands are under qualification. Legacy source
migration, package schema compatibility and complete lifecycle integration are
not yet qualified for rollout.

A declaration names a key and its format. Its Draft, Staging and Production
values are separate. A development operator can declare and bind a key without
receiving its value; an authorized configuration operator fills the value in
**Project → Environments** and approves its consumer and destination.

The central page supports search, paginated status, comparison between authorized
environments, individual replacement/clear, atomic batch entry, usage and legacy
mapping review. Editors start blank. Sensitive requests do not enter React Query
mutation caches. Leaving an editor requires discard confirmation; reload or close
warns about unsaved input. Submission failures clear input and show a sanitized
message, never an upstream body. Broader navigation and accessibility qualification
is still in progress.

Provider creation and the current HTTP/MCP Tool form accept references. Tools
support API key, Bearer, Basic, named headers and explicit public access. Save the
connection first; MCP discovery is a separate action after values and use approvals
are available. Existing legacy connections retain their migration boundary.

With a compatible CLI:

```sh
woobe project configuration declare PRIMARY_API_KEY --kind secret --format token
woobe project configuration bind provider CREDENTIAL_UUID --key PRIMARY_API_KEY
woobe project configuration list --env staging
woobe project configuration check agent AGENT_UUID --env staging
woobe project configuration check tool TOOL_UUID --env draft
woobe project configuration test provider CREDENTIAL_UUID --env staging
woobe project configuration test tool MCP_TOOL_UUID --env draft
```

`check` reads metadata. `test` makes external calls: Provider model discovery or
MCP discovery. Neither command runs an Agent or deploys Production. Tool tests in
this group do not invoke arbitrary HTTP operations. The CLI negotiates
`project_configuration.v1`; an unsupported server fails before mutation and no
local `.env`, credential file or secret store is used as a fallback.

Readiness separates material (`missing`, `present`, `invalid_format`, `revoked`,
`unavailable`), external validation and legacy source. A configured value alone
does not prove a connection is valid. Legacy or unresolved closure is reported
as unknown until its mapping is established.

Permissions separate read, declare, bind, value write/clear, use-policy write,
external validation and migration. Permissions on a Provider or Tool do not alone
permit changing its referenced values. Owner transactions recheck the required
authority. An Environment-specific permission does not authorize metadata from
other Environments.

See [the architectural decision](adr/0005-project-configuration-authority.md).

The [migration runbook](runbooks/PROJECT_CONFIGURATION_MIGRATION.md) describes
the bounded Provider job, process inventory, revision guards and recovery. Its
completion does not yet qualify migration of the other legacy source families.

## Portable structure without values

Package schema `2.0` declares `spec.configuration.keys` and `spec.connections`.
Connection authentication contains only remote references such as
`{source: project_environment, key: PRIMARY_API_KEY}`. The separate `1.0`
catalog, its canonical digest and existing operational imports remain unchanged.

A `2.0` import requires explicit `installation_mode: structural` and Draft.
The plan declares keys before creating Provider connections and dependent Models,
Tools, Agents and Networks. A destination key or Provider is reused only through
an explicit binding; a same-name collision is rejected. No protected local values
are accepted. Missing values do not trigger discovery or embeddings during import.
Portable Knowledge records its frozen document selection and vector build intent
as `PENDING_PREPARATION`; normal Workers do not claim that status. Release and
runtime validation still require READY Knowledge.

The receipt separates `installation_status`, `configuration_status`,
`runtime_preparation_status` and `deployment_status`. Structural completion is
not execution readiness or deployment. Draft structure can be exported as `2.0`
before values or external preparation exist; exports include declarations and
references, never central material or legacy alias authority.

The CLI negotiates the catalog digest and structural capability before writes:

```sh
woobe package export agent AGENT_UUID --package-schema 2.0
woobe package plan ./support --structural --save-plan ./support-plan.json
woobe package import --plan-file ./support-plan.json --wait
```

Qualification remains in progress: complete legacy-source migration and lifecycle
readiness must pass before this feature is released.

### Knowledge preparation

`POST /agent/knowledge/vector-snapshots/{snapshot_id}/prepare` queues a declared
snapshot after checking its `expected_build_config_hash`, Project, Environment,
Model/connection revision and use grants. It requires `knowledge:write` and
`project:environment:validate` in the owner transaction. Requests without values
or use approval leave the snapshot pending. Retrying an accepted request does not
create another build; changed or failed intents require a new version.

The vector Worker uses the central pinned credential at each actual transport
send. Metadata reads and progress writes use short transactions. Parsing and
embedding calls hold no SQL transaction. Chunks, document projections and READY
commit together under the Worker ownership and frozen-document guards. A stale
Worker cannot commit results or overwrite its successor's terminal state.

Structural Network installation imports captured Agent definitions into Draft and binds destination nodes to those Drafts. The approved plan records `constituent_binding_policy: imported_draft`; it never creates constituent Staging or Release snapshots as an incidental installation effect. The original source selectors remain in the approved source evidence. Preparation authorization is stored separately from the immutable vector build configuration and does not change its hash.

### Contextual runtime status

Agent and Network Playgrounds read configuration metadata for the selected environment and exact saved snapshot. The compact notice separates missing material, unreadable status, denied access and outstanding external checks. Details expand on demand. Unsaved Draft edits are explicitly outside that saved-definition result; Acceptance remains responsible for authorizing the actual submitted closure. Refreshing or returning from Environments never executes a Run. After a value is saved, cached readiness is invalidated.

Legacy header references accept a whole `{{secret:name}}` value. Missing/unreadable material, empty values, header control characters and ambiguous partial templates fail before sending a request. They no longer silently become an empty header. These guards do not replace the remaining source migration and destination-policy cutover.

### Managed development and immutable history

New CLI clients select Package 2.0 for managed `pull` only when the server
advertises the matching ASaC definition scope and package catalog. Public Provider
YAML retains typed remote references; native connection IDs stay in destination
state. Local validation, structural Draft push, isolated Draft checkpoint and
Candidate preparation preserve those references without reading local variables.
Older servers retain the schema1 workflow; a mismatched advertised schema fails
before writing and never causes an implicit downgrade.

Schema2 history uses a separate digest contract documented in
[ASaC history](runtime/ASAC_HISTORY.md#configuration-aware-portable-definitions).
Capturing or preparing a revision is not permission to execute it or populate
missing remote values. Full lifecycle and legacy-source qualification remains
part of the rollout gate.


Legacy Provider creation now places material in the central store in its first
transaction. The existing Provider ID remains stable and receives an explicit
compatibility alias restricted to that consumer and its declared destination.
It does not copy the value to all Environments or authorize generic references.
Existing database rows still require the inventory/cutover workflow. Unsupported
or ambiguous destinations fail without retaining an active inline credential.
Material rotation preserves the semantic binding revision; configuration-aware
ASaC guards compare that revision separately from value versions.

Network configuration admission reads the exact pinned Agent release, including
when a Network carries only a compatibility override with provider/model names.
Fallback model preparation preserves the protected resolver until HTTP send;
revocation and destination checks apply to fallback requests as well.

## Activation evidence

Candidate preparation seals an immutable artifact independently from Environment
configuration. Its package operation reports `lifecycle_state: candidate` and
may succeed with `configuration_ready: false` and `execution_ready: false`.
Inspect readiness for the exact Candidate snapshot in Staging; inspection does
not authorize a Candidate Run. Running its evaluation still requires every
mandatory configuration dependency.

Native Production activation and rollback qualify the exact Agent/Network
closure inside the committing transaction. ASaC deployment plans additionally
retain metadata evidence for the selected Environment: declaration revisions,
consumer definitions, use-policy revisions and opaque material versions. Apply
rechecks that evidence under the same configuration locks. Rotation after plan
creation requires an explicit new plan, even if the new value is usable and the
immutable Release has not changed. A blocked or stale activation leaves the
current selection and activation outbox unchanged.

Configuration errors use `configuration_schema_version: project_configuration.v1`
and bounded code/key/Environment diagnostics across canonical API operations.
Provider error bodies and submitted values are never part of that contract.

A legacy custom Provider can still be created before its endpoint is selected.
Its secret moves immediately to central storage, but no destination is implicitly
authorized. An operator must set the destination and approve its usage policy
before execution. A Model overriding the endpoint does not grant that approval.

Retained Web author objects use their original package schema. For schema2,
server-generated Web bindings reuse the captured Provider identities and declared
keys; editing a file does not create a credential or import a value. Explicitly
reusing a central legacy Provider preserves that connection's compatibility route
and reports `binding_source: legacy_configuration` in planning evidence. It does
not authorize another consumer or make a plain Environment reference resolve a
legacy value. Readiness still identifies the actual selected material source.

Typed HTTP Tool authentication accepts parameterized query/path values under a
static scheme, host, port and path prefix. Approve that prefix explicitly in the
use policy. Host/scheme templates remain invalid; every rendered outbound URL is
rechecked for destination changes and encoded path traversal before credentials
are attached. URL template edits also change the binding revision.

## Project summary

`GET /core/projects/{project_id}/configuration/summary?environment=draft` is a
metadata-only observation of current Agent/Network selections in one Environment.
It checks configuration-read permission and each inspected owner's read authority
before returning aggregate counts. It never decrypts values or starts external
validation. Targets without a Staging/Production selection are counted separately;
they do not create a missing-secret alarm in another Environment. Structurally
installed inactive Agents can be diagnosed, but remain ineligible for execution.

The Overview follows its chosen Environment. With Overview set to All, the compact
configuration strip defaults to Draft and remembers an explicit per-Project choice
for the browser session. It refreshes on focus, every 30 seconds and after central
configuration writes. Permission loss or failed refresh hides prior counts. The
link returns to the same Project after editing, without rerunning any operation.

The summary inspects at most 50 Agents and 50 Networks per request. A larger or
unresolved closure reports `unknown` / `complete: false`, never a partial green
status. Use exact target readiness for execution decisions. CLI clients discover
the optional `project_summary` capability before requesting this projection.

The central metadata inspection is batched across the authorized target closures:
keys, Environment slots, policies and validation evidence are read once per
observation (with additional bounded reads for legacy aliases). Different
resource revisions are evaluated independently. This batching creates no leases
and does not relax the single-closure revision checks used by actual admission.

New Web isolated Drafts default to **Remote references** (Package 2.0). Existing
unmigrated connections can be captured by explicitly choosing **Legacy
compatibility**; a failed remote-reference capture never silently retries under
a different contract. Retained edits preserve their original package version.

New legacy Secret API writes also create their central alias in the same first
transaction, retaining the Secret ID/name while clearing entity ciphertext.
This does not grant every Tool access. An old Tool write which introduces a new
recognized Secret-header consumer requires current `secret:read` and
`project:environment:use-policy:write` authority for all compatibility routes.
Without that authority the Tool write rolls back; use the reference-only workflow
or ask an authorized configuration operator to establish the connection. Existing
captured routes survive metadata edits, including their deliberate revocations;
a Tool edit cannot implicitly re-grant a revoked central policy.

Retained Tool snapshots keep their original bytes and hashes. Execution reapplies
only the Project-scoped references captured during Acceptance; the transport
still checks the Tool, field, destination and Run lease before resolving material.
MCP creation with a Secret template reports `configuration_required` and defers
discovery to explicit connection preparation, after use approval and outside SQL.

The existing persisted-Tool execute and MCP refresh routes also support these
central references. They retain their response contracts and use Draft, as their
legacy inputs have no Environment selector. Execution requires Tool execute
authority; central MCP refresh additionally requires configuration validation
authority. Both acquire the current destination grant before external I/O and
fail on revocation. Use the configuration preparation route for an explicit
Staging/Production check. Invocation-local headers cannot spill into another Tool.

These two composers expose detached callable boundaries, covered by the
architecture gate: they own no global UnitOfWork. Legacy compatibility handlers
are created lazily only for definitions that have not been converted. A central
failure never falls back to that path.

New legacy HTTP/MCP Tool writes move explicitly sensitive global header literals
(and standard authorization/API-key headers) into central storage before the
first commit. Tool definitions and responses retain only the owner's reference;
MCP discovery waits for explicit preparation. A legacy replacement rotates the
same alias. It does not grant a new destination, restore a revoked use policy, or
choose an Environment after that alias was split. Metadata-only edits retain the
reference. Clients must use the configuration binding operation to change a
reference; they cannot submit another Tool's private compatibility alias.

This writer does not migrate retained inline snapshots or promote route-local
headers to global authority. Those sources still need owner-specific migration
and historical evidence handling before storage contraction is qualified.
