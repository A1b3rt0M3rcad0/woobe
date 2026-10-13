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
