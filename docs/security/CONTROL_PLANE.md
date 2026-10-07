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
The browser exposes this management under **Workspace settings → CLI Keys**.
Creation places identity fields in one horizontal row, followed by adjacent role
and expiration panels. Active predefined and custom authority categories are
loaded from the backend, including every category page. Choosing a role pins its
category ID and revision; Project grants preserve or narrow inherited conditions.
Roles exceeding the issuer's permissions or having incompatible restrictions
are disabled rather than silently reduced. Advanced custom permission selection
remains available. Workspace and Project roles remain separate grants.
Expiration defaults to 90 days. The inline calendar selects only a date, with
no time controls; the key remains usable throughout the selected local day and
expires at the following local midnight, serialized as an aware UTC instant.
Workspace owners and admins with the required effective key permissions can
list, create, rotate and revoke keys there. Creation uses the live permission
catalog and separate Project grants; no role or permissions are selected by default.
Existing assignment restrictions are carried into delegated Project grants.
The backend remains authoritative for every issuance and mutation.

Issued secrets are revealed only in the current view and are excluded from
frontend query/mutation caches and development payload logs. Copy the secret
before dismissing that view; closing the modal, switching tabs or changing
Workspace removes the view. The panel provides credential import and Workspace
context commands for `woobe-cli`. Rotations replace the secret immediately;
rotation and revocation use the observed strong ETag. Project Runtime Keys
remain separate credentials for Agent and Network execution.

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

## Advertised CLI validation contracts (2026-10-05 continuation)

The CLI can opt into request-body validation and separate path/query validation.
These checks use OpenAPI DTO schemas and supported serialization rules; they do
not authenticate, authorize, coerce values on behalf of the server, or reproduce
custom DTO validators. Backend authority and transactional rechecks remain the
source of truth. Parsing/dispatch still happens through the existing handlers.

Previously opaque Agent/provider/model, prompt/contract, Knowledge, Tools,
session/message/job and identity writes now advertise their existing DTO input
schemas. Nested DTO definitions use document-relative pointers into each inline
request schema. Path identities are separately described; Agent session list
parameters reflect the actual project/environment/cursor/limit DTO consumed by
the controller. Exporting metadata does not introduce a new persistence path.

The live CLI acceptance now requires body validation for provider/model/Agent
creation, body and path validation for Agent edits, and advertised query/path
validation for constrained session pagination. Unsupported DTO schemas or
parameters must fail before the operation rather than silently approve input.

Worker health probe diagnostics report safe reasons and stopped worker indexes,
never arbitrary heartbeat payloads or worker errors. The failed historical smoke
at 0aa81da was followed by successful smoke/restart on a74ebc9; its root cause
was not reproduced and is not asserted fixed by adding diagnostics.

## Declarative category definitions and immutable comparison

The CLI resource kind `AuthorityCategory` belongs to a Workspace, even when its
permission scope is Project. Category-only documents do not require a selected
Project. Definitions import through the existing category create/update endpoints
and do not issue credentials, materialize grants or assign humans. Updates require
an explicit category ID and current strong ETag; existing grants retain the
original category revision. Clone/archive/delete and assignment remain explicit
operations outside the category resource import.

`workspace authority category diff` reads two explicit immutable revisions. It
compares concrete permission and condition sets without relying on array order;
it does not migrate grants or enumerate every affected assignment. Selective
capture preserves the observed ETag. Skip-unchanged requires matching category,
Workspace, revision and strong ETag. A saved successful checkpoint suppresses a
repeated create; there is no name-based upsert or category-create replay promise.

Additional DTO contracts now describe Knowledge collection edits/versioning and
vector build/preview, Tool status/test/execute, MCP discovery/refresh/permission
modes, provider credential rotation, release promotion/rollback, runtime ask and
Workspace edits. Fields injected from path parameters are omitted from the body
schema and advertised separately. Schema traversal distinguishes annotation
literals from property names that happen to be JSON Schema keywords.

MCP permission modes remain `allow`, `deny` and `review`. Advertising Tool/MCP
execution input does not confer execution authority. Release DTO preflight does
not replace publication lifecycle rules, including required production notes.

## Protected CLI inputs and MCP permission validation

The CLI can resolve exact protected credential references for Tool and provider
configuration at apply time. They are local POSIX private-file references, not
server-side secret handles. The backend receives the normal DTO field value and
retains its encryption, ownership and projection rules. Checkpoints bind the
local value snapshot; redacted reads cannot certify an uncertain secret write.
No category import, protected reference or client validation grants authority.

MCP permission DTOs accept only allow/deny/review and forbid unknown fields,
blank/padded names, duplicate remote names and empty/unbounded selective lists.
The application requires a valid MCP provider discovery and checks the entire
selection before mutating anything; an unknown remote name rejects the whole
request. Bulk updates affect exactly the discovered provider set. Review keeps
remote capabilities unavailable and does not introduce a per-call approval UI.
Existing immutable release tool snapshots retain their policies.

Reviewed DTO query contracts cover Agent/provider/Knowledge/Tool metadata and
session messages. Message pages use offset 0..1,000,000 and limit 1..1000.
Skill imports and catalog paging, and the six existing MCP OAuth operation bodies,
are advertised without moving parsing ahead of authorization. Custom validators,
network readiness and OAuth success still require backend evaluation.

## Complete CLI discovery contracts

The pinned client discovery has a server operation for each of its 190 HTTP
commands. Adapter-based routes advertise missing path placeholders as strings;
explicit DTO and typed handler constraints remain intact. The existing
`/ai/context-assemblers` alias is included in discovery alongside the canonical
context manager catalog.

Project edits, environment values, invitations, Project access, key issuance,
key credential edits and Agent release creation advertise their consumed inputs.
API key rotation advertises its existing optional body and supports the CLI's
bodyless invocation. Principal-derived key actors are omitted from client body
schemas; controllers continue to derive them from authentication. Commands whose
controllers ignore a body advertise an optional object rather than invented
domain fields. Schema preflight does not bypass authentication, authorization,
custom DTO validators or resource lifecycle checks.

Project edits update the persisted row rather than reinserting its primary key.
Each successful edit emits a distinct transactional outbox event, allowing
successive edits without violating event deduplication constraints. The live CLI
acceptance verifies successive edits and preservation of Project identity and
creation time.

### CLI Key self-discovery

`GET /identity/control-key/me` uses the authenticated Control Key's `access:self`
authority. It requires no Workspace/Project IDs and no `workspace:read` permission.
The versioned response contains only that key's public metadata, active Workspace
and current Project grants, including status, permissions, conditions and category
provenance. Inactive or empty grants are marked ineligible for CLI selection.
The secret is never returned. Authentication checks expiry/revocation and active
Workspace before discovery; all subsequent operations independently enforce grants.
This endpoint neither grants permissions nor supports Runtime Keys/human sessions.
