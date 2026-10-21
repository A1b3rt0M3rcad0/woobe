# Artifact authorization

Artifacts reuses `AuthenticatedPrincipal`, `ControlPlanePrincipal` and
`ProjectApiPrincipal`. No new users, password store or credential system exists.
The authority catalog adds explicit `artifacts:{read,search,write,delete,process,
transfer,manage}` permissions at Project scope and an artifact-editor profile.
Current authority category snapshots keep their existing immutable revisions.

`ArtifactAuthorization` is the single operation decision used by application
capabilities. It requires the current credential's Project/Environment, a current
Workspace/namespace grant and the requested action. Runtime Keys additionally
need the explicit `artifacts` interface. Merely having `runtime:execute`, knowing
an ID or supplying External Context grants no file access. Project API keys do
not acquire the Runtime/administrative roles. Grants use prefixed existing
credential/user IDs and never contain credentials.

Release permissions, node delegation and the bound Workspace can only reduce
the credential/grant decision. Expired/revoked grants and credentials fail closed.
Archived Workspaces permit only read/search/management; deletion-pending/purged
Workspaces are unavailable through data operations. Cross-scope and unknown
Workspace selection yield the same safe access-denied response.

The SQL adapter calls the existing shared TenantAuthorizer. It revalidates human
session lineage and Control Keys using the existing methods; a new shared
`require_active_runtime` checks the current Runtime Key row, Project status,
expiry/delegation expiry, target binding, interface and scope without retaining
the raw key. Live grants are read under row share locks and refreshed from the
database. Callers must authorize again in each short read/write/publication or
transfer transaction; admission is not irrevocable authorization.

Administrative provision/grant management requires explicit Project authority.
Runtime namespace provisioning also needs a namespace grant. Browser consumers
must receive restricted server-issued credentials; a broad application credential
is never placed in a browser. GrantRepository is an internal persistence adapter,
not a public unauthenticated grant API.

The HTTP guard recognizes the reviewed Artifacts resource families as the
`artifacts` Runtime interface; they do not execute a Run or activate `/v1/jobs`.
The Artifacts operation handlers and administrative operation catalog are wired
in the API delivery step. Classification by itself exposes no endpoint or grant.

Step 05 evidence: the action/scope/interface/expiry/revocation/Release/node unit
matrix and existing authority/routing regressions passed. Fourteen real PostgreSQL
cases verify grant revocation after admission and retained-principal denial after
key revocation, expiry, delegation expiry, interface removal or Environment change,
on both fresh and populated-upgrade databases. No synthetic fixture is claimed as
complete API, browser or live-provider qualification.
