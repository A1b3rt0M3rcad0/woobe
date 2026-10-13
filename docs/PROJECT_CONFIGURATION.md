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

Qualification remains in progress: the preparation/resume workflow and ASaC
binding fingerprints must be completed before this feature is released.
