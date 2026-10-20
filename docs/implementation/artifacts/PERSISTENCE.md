# Catalog persistence

Migration `0107` adds the `artifacts` PostgreSQL schema with Workspaces, logical
Artifacts, immutable revisions, half-open catalog head history, scoped grants and
recoverable upload records. Its DDL is frozen in the migration rather than
importing mutable ORM models. Alembic discovery includes the new managed schema.

Workspace external identity is unique within Project/Environment/namespace.
Live paths are unique within their Workspace. Composite foreign keys prevent a
file's head/history from pointing at another Artifact's revision, or a revision
from naming an Artifact in a different Workspace. A PostgreSQL trigger rejects
revision updates. Logical removal will be governed by lifecycle services; history
is not an irrevocable right to read deleted content.

Project IDs remain cross-context identities validated by the existing authority,
following migration `0018` rather than importing Core ORM tables into Artifacts.
Internal Artifacts foreign keys are restrictive. No foreign key makes a Workspace
dependent on a Session/Run or causes it to disappear when a conversation ends.

`CatalogRepository` always requires scope and Workspace identity. Mutation locks
the Workspace row, refreshes its current state, checks the expected revision,
advances its monotonic catalog version and stores a new half-open head interval
in the same short Unit of Work. Two writers with the same expected revision
produce one winner and one conflict. Rollback leaves neither a revision nor a
quota/catalog advance. Quota includes all retained revision bytes, not only the
current head. Upload reservations are accounted separately.

Historical listing selects visible head intervals by version using indexed
Workspace predicates. It never copies the Workspace inventory into a Run, and
also checks current logical deletion. Source reads never silently substitute a
newer revision for an unavailable exact revision. SQL metadata alone does not
announce an HTTP or storage capability; authorization and adapters follow in
the next steps.

## Real PostgreSQL validation

Set `WOOBE_ARTIFACT_TEST_POSTGRES_URL` securely to an authorized local test
PostgreSQL cluster with pgvector and permission to create disposable databases.
Never put its value in source or logs. Run:

```sh
.venv/bin/python -m pytest -q tests/integration/artifacts/test_catalog_postgres.py
```

The fixture creates randomly named databases, validates both fresh migration and
upgrade of a populated `0106` baseline, repeats upgrade, and drops only its own
databases in teardown. The regular Compose test environment can use its existing
`WOOBE_POSTGRES_URL` when `WOOBE_ENVIRONMENT=test`; other environments require the
explicit test URL. Missing configuration is reported as skipped, never as passed.

The step 04 run executed all 14 cases on real PostgreSQL: migration/data retention,
historical selection, database revision immutability, rollback, concurrent CAS,
scope isolation, unique identity/live paths, revision ownership, logical deletion
and index availability. The tiny-fixture EXPLAIN forces index consideration to
verify usable indexes, not to claim production-scale latency. Scale qualification
remains step 57.

The shared SQLAlchemy registry uses the unique class name ArtifactWorkspaceModel
for the Artifacts table. A repository-local WorkspaceModel alias does not register
another class. Identity WorkspaceModel and its existing string relationship retain
their exact meaning. Isolated subprocess tests load both contexts in both orders
and configure the real ORM relationships; this guards a collision found by the
full existing backend integration CI, beyond the isolated catalog suite.
