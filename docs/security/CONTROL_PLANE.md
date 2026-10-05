# Control Plane authority

Workspace is the ownership boundary. Project grants authorize management of
resources within that Workspace. A Control Key uses the `woobe_control_` namespace
and authenticates a machine principal; it is distinct from human sessions, Project
API Keys, target-bound Runtime Keys and ChatSurface Access Keys.

## Permission discovery and decisions

`GET /identity/permissions` returns the versioned permission catalog and the
reviewed HTTP method/path pairs. An unreviewed operation is unsupported for
Control Keys. Runtime submissions are advertised as execution effects. Network
promotion preview requires the same environment authority as promotion: staging
uses `network:version`, and production uses `network:production`. A prefix match never grants authority to a future endpoint.

`GET /identity/access/me` accepts `workspace_id` and optionally `project_id` and
returns current permissions, conditions and category provenance. Human callers
must supply a Workspace. Control callers default to their own Workspace.

`POST /identity/access/check` accepts `method`, `path`, `query` and `body` and
evaluates the same tenant and authority policies as the HTTP guard without
performing the operation. It reports authorization, not DTO validity, lifecycle
validity or a reservation for a subsequent write. Reauthentication and permission
checks occur on the actual request.

Resource identifiers are resolved to their owning Project and Workspace before
management handlers run. A Runtime Key cannot manage resources, and a Control Key
cannot execute a Run through runtime endpoints. Use a separately selected Runtime
Key to execute, stream or cancel a target. Viewer membership denies mutations
even when an authority assignment contains a write permission.

## Categories, grants and delegation

Workspace-owned categories are managed at
`/identity/workspaces/{workspace_id}/authority-categories`. A custom category has
immutable revisions, a current revision and active/archived status. System
profiles can be cloned; their definitions cannot be edited. Wildcards require
the current catalog revision and are expanded into concrete permissions when a
revision is created. They do not authorize future catalog additions.

Control Keys are managed at `/core/workspaces/{workspace_id}/control-keys`.
Workspace permissions and Project grants are separate. A grant can copy a
category revision and its conditions. Later changes to the category do not
silently change issued keys or human assignments. Grant and assignment provenance
retains the category ID and revision. Referenced revisions cannot be deleted.

Conditions restrict environments, target types, target IDs and runtime interfaces.
Delegation must preserve or narrow every restriction; removing a constrained
dimension broadens authority and is rejected. Arbitrary body IDs cannot turn an
unfiltered collection operation into an authorized target-specific request.
Equivalent UUID representations are compared using their canonical identity.

Conditional reads of stored Agent Runs, Runs resolved by trace, Network executions
and Network session history use the persisted target and runtime environment.
A supplied body or query environment cannot replace that stored environment, and
a session under a different Network cannot be selected through a parent path.
Environment-restricted runtime grants deny collections whose environment is
unknown. Run-list filters (`agent_id`, `session_id`, `environment`) and active
Network execution filters (`network_id`, `network_session_id`, `environment`) are
used by authorization because those exact handlers consume them. Unrelated query
parameters do not narrow an unfiltered operation. Preflight uses the same filters
and persisted resource checks as actual requests.

Creating a Project with a Control Key materializes only its explicit
`on_project_create_permissions`. Creating or rotating a Project/Runtime Key checks
the issuing Control Key's grant, requested runtime scopes, binding and expiration.
The delegated expiration ceiling is stored on the issued key and preserved across
human and machine rotations. Rotating a credential cannot extend its delegated
lifetime. Child Control Keys retain their delegation ceiling and parent credential
lineage across rotations.

An inactive Workspace blocks both human authority and delegated credential
issuance. Issuance rechecks the Control Workspace inside the transaction.
Administrative Control authority is checked against locked current permissions,
expiration and delegation ceiling; a changed authenticated snapshot requires
reauthentication. Owner discovery reports structural authority without applying
restrictions from an assignment retained after promotion to owner.

## Revision preconditions

Category and Control Key mutations use strong resource ETags:

| Resource | ETag |
| --- | --- |
| Category | `"category:{id}:{revision}"` |
| Control Key | `"control-key:{id}:{revision}"` |
| Human assignment | `"assignment:{id}:{revision}"` |

Send the observed ETag in `If-Match`. Missing preconditions return HTTP 428;
malformed, weak, wrong-resource or stale preconditions return HTTP 412. To create
an assignment, use `If-None-Match: *`; updates require its current ETag.
Creation and update headers cannot be combined, and duplicate revision headers
are rejected. The catalog advertises assignment creation/update preconditions.
Revisions and revision selectors are positive integers bounded by the database
range (2,147,483,647). System-profile history observes the same exclusive revision
cursor as custom category history.
Category history and audit responses contain their own pagination/completeness
fields. Callers must not infer collection completeness from HTTP success.

## Administrative idempotency

Supported administrative creation and Control Key rotation paths accept
`Idempotency-Key`. Records bind Workspace, authenticated credential lineage,
operation and payload in the same database transaction as the mutation. Reusing
the key with another payload returns HTTP 409. A completed replay returns the
original result and `Idempotency-Replayed: true`, without repeating the write.

Responses containing issued secrets are encrypted for replay retention of 24
hours. Expired replay attempts return conflict and require reconciliation; they
do not restart the operation. This mechanism does not promise idempotency for
every management endpoint. An authorized resource read alone does not prove who
performed the original write.

## Validation

The backend Compose contract runs unit tests and PostgreSQL integration tests.
The backend CI also compiles the pinned Go CLI revision and requires a live CLI
workflow against the API, workers, fake model provider, PostgreSQL, Redis,
RabbitMQ and MongoDB. Tests create Agents and Networks through public commands,
publish immutable releases, execute with separate Runtime Keys and verify
authorization refusals and recoverable administrative writes.

See [Compose tests](../testing/COMPOSE_TESTS.md) for the exact invocation and
local CLI setup. CI success certifies the tested revision and scenarios; it does
not certify all CLI manifest, pagination, credential-provider or stream-recovery
features.

## Agent session listing

The reviewed administrative GET /runtime/agents/{agent_id}/sessions requires
run:read in the Agent's owning Project. It lists existing sessions and does not
execute the Agent. Project consistency and target constraints remain enforced
through the same ownership guard.

The environment query is the actual collection filter. Authority evaluates its
effective value, including the handler's default draft environment when omitted
or empty. A staging-only key must explicitly query environment=staging; it cannot
use omission to read draft sessions or query production. Unreviewed routes do not
gain authority from arbitrary environment query values. This catalog addition is
recorded in revision 2026-10-05.2.
