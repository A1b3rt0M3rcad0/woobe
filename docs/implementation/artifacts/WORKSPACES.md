# Independent Workspace operations

Core now exposes create, resolve, get, list, CAS update and explicit grant-management
capabilities through zero-argument composers in the Artifacts entrypoint. Each
uses the existing TransactionalHandler and a short Artifacts Unit of Work;
application use cases depend on authorization and repository ports, not SQL/HTTP.
HTTP endpoints and client commands are delivered in their subsequent steps.

A Workspace can be provisioned with no Agent execution, Session or Run. Its
external namespace/key is opaque and unique within Project/Environment. Storage
profile is fixed at creation. Arbitrary friendly labels are bounded metadata,
not application-specific domain entities or authorization evidence.

Concurrent retries of the same creation payload return one Workspace. Different
payloads for the same scoped external identity conflict. Migration `0108` retains
the canonical creation fingerprint, including normalized label ordering, so later
rename/metadata changes do not break recovery from a lost creation response.
Internal entries created before the receipt contract should be resolved explicitly;
a missing original receipt is never guessed from changed current metadata.

Updates require expected_version and cannot change Project, Environment, external
identity or storage profile. Unchanged metadata is a no-op; a real update advances
the CAS version. Archived Workspaces reject data mutations. deletion_pending is
terminal for ordinary metadata updates and prevents new data operations; physical
purge is delivered by the retention/lifecycle step, not a synchronous metadata edit.

Listing applies current grant, Project, Environment, namespace and principal
filters in SQL before keyset pagination. Signed, versioned cursors are bound to
principal, query and purpose, and cannot be transplanted between filters or
credentials. Pages report explicit continuation/has_more. As with standard keyset
pagination, concurrent insertions require a refreshed listing to discover entries
inserted before an already-consumed cursor; listing is not a global Workspace
inventory snapshot. A Run's artifact catalog snapshot is a separate later contract.

Administrative provisioning requires current Project Artifacts management authority.
A creator receives a scoped Workspace grant; each later action still requires its
current Project permission. Runtime provisioning additionally requires a namespace
grant and never creates broader grants for itself. Only current administrative
authority can delegate/revoke grants. A retry does not resurrect a revoked creator
grant. No broad application key is exposed to browser clients.

Step 06 validation executes Workspace races, conflicting creation, resolution,
CAS, receipt replay after rename, deletion-pending refusal, SQL-filtered pagination,
cursor tampering and cross-principal/filter/Environment reuse, label ordering and
a real public composer against PostgreSQL. Existing catalog and live-credential
tests also run on both fresh and populated migration paths. Domain/schema/cursor
tests and architecture gates remain separate checks.
