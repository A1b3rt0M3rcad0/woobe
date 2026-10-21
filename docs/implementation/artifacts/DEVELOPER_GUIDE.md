# Artifact Workspaces developer guide

Artifacts are Project-scoped files with immutable revisions. A Workspace exists
before a Session and can be used through the direct API/SDK or through an Agent
or Network Run. External Context selects a logical Workspace; current grants
authorize every operation. A binding or old Run snapshot never replaces current
authorization.

## Bring up a validation stack

The default Compose stack includes native text/PDF processing and structural
indexes. Optional parser/PageIndex profiles are explicit:

```sh
docker compose -f compose.yaml -f compose.artifacts-documents.yaml config --quiet
docker compose -f compose.yaml -f compose.artifacts-pageindex.yaml config --quiet
```

See [deployment profiles](DEPLOYMENT_PROFILES.md) before enabling an optional
worker capability. Check `/v1/artifact-capabilities` and
`/v1/artifact-processing-capabilities`; an uninstalled processor is reported as
unavailable, while store-only uploads remain usable.

## Direct application access

Create a Workspace with a stable application namespace/key, upload a bounded
file, and keep the returned exact Artifact and revision IDs. The direct Go
client is created with an explicit Project, Runtime Key and Environment; the
Python client uses the same scope. Neither client creates a Run or Session for
file operations, and neither accepts an administrative Control Key.

- [Go SDK Artifacts example](../../../clients/woobe-sdk-go/examples/artifacts/)
- [Python SDK Artifacts API](../../../clients/woobe-sdk-python/README.md)
- [CLI Workspaces guide](../../../clients/woobe-cli/docs/ARTIFACT_WORKSPACES.md)
- [Public HTTP routes and limits](HTTP_API.md)

Uploads are resumable through an idempotent operation ID and acknowledged part
offsets. Downloads name an exact revision and verify the declared size and
SHA-256. Search results contain immutable SourceRefs; open the referenced source
through the authorized bounded reader rather than substituting the latest file
revision. See [uploads](UPLOADS.md), [authorization](AUTHORIZATION.md),
[search](SEARCH.md), and [document indexes](INDEXES.md).

## Agent and Network access

Configure an Agent/Network with a logical Workspace binding, required actions,
and an optional pinned processing profile. Acceptance resolves the binding
from External Context and persists the Workspace/catalog snapshot for that
Session or Network execution. Start another Session for another logical
Workspace; do not place private Workspace IDs, credentials or signed URLs in a
portable Agent/Network definition.

Runtime requests may contain text and exact Artifact revision parts. Search,
tree navigation and source reads are bounded Tools; citations retain their
original revision and locator. A later Run can consume an explicitly published
output Artifact. See [Runtime binding](RUNTIME.md),
[Network execution](NETWORK.md), [representations](REPRESENTATIONS.md), and
[model processing](MODEL_PROCESSING.md).

HTTP and MCP transfers require an approved contract and explicit transfer
limits. A redirect, expired grant, changed revision, checksum mismatch or
uncertain delivery is surfaced as a failure/uncertain outcome; do not blindly
retry a non-idempotent external write. See the SDK/CLI recovery guides and
[observability](OBSERVABILITY.md).

## Validate changes

Use the disposable PostgreSQL runner for database-backed Artifact tests. It
creates isolated databases, exercises a fresh schema and a populated legacy
schema, and drops them afterward:

```sh
PYTHONPATH=.:packages/woobe-core/src:packages/woobe-api/src:packages/woobe-workers/src \
  .venv/bin/python /workspace/.onboarding/run_artifact_tests.py -q \
  tests/integration/artifacts/test_http_postgres.py \
  tests/integration/artifacts/test_runtime_workspace_binding_postgres.py
```

The fixed provider-neutral evaluation corpus is checked with:

```sh
PYTHONPATH=.:packages/woobe-core/src:packages/woobe-api/src \
  .venv/bin/pytest -q tests/unit/artifacts/test_evaluation_corpus.py
```

These tests validate source contracts and the deterministic adapter boundary.
They do not report live-provider, OCR quality, semantic-generation or production
scale qualification. Optional S3 tests require an explicit isolated local test
endpoint. The no-key scope is recorded in [plan adjustments](PLAN_ADJUSTMENTS.md).

## Operate and recover

Keep database migrations at head during an application rollback; never run a
destructive downgrade to disable the feature. Use the lifecycle worker for
retention and purge, retain independent tombstone history, and restore into an
isolated target before serving it. Follow [upgrade and rollback](UPGRADE_ROLLBACK.md)
and [backup, export and restore](BACKUP_RESTORE.md). Export manifests contain
authorized current revisions and hashes; they are not a full historical backup.
