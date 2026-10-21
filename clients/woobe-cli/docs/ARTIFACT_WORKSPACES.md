# Artifact Workspaces

The CLI operates the public Artifact API with a Runtime Key scoped to a Project
and Environment. It never falls back to a Control Key and does not require an
OpenAI API key. Use a context with an attached Runtime credential, or provide
`WOOBE_RUNTIME_KEY`; the server still checks the key's Artifact grants on every
request. Bind an explicit Project to the context or pass `--project`.

```sh
woobe artifacts workspace list --project PROJECT --environment staging --output compact
woobe artifacts workspace create --project PROJECT --environment draft \
  --external-namespace app:customer --external-key customer-123 --name "Customer files"
woobe artifacts workspace resolve app:customer customer-123 --project PROJECT --environment draft
woobe artifacts workspace get WORKSPACE_ID --project PROJECT --environment draft
```

Workspace creation uses the external namespace/key as the stable identity. List
and search responses retain the server's `has_more`, `next_cursor` and
`truncated` markers. Pass the opaque `--cursor` back unchanged; a page is not a
claim that the full collection was read.

```sh
woobe artifacts list WORKSPACE_ID --directory invoices --limit 50 --output compact
woobe artifacts get WORKSPACE_ID ARTIFACT_ID
woobe artifacts revision WORKSPACE_ID ARTIFACT_ID REVISION_ID
woobe artifacts search WORKSPACE_ID "retention policy" --mode hybrid --limit 20
woobe artifacts tree WORKSPACE_ID INDEX_ID --limit 50
woobe artifacts read-node WORKSPACE_ID INDEX_ID NODE_ID --offset 0 --max-chars 8000
```

Search returns exact immutable SourceRefs. Save one `source` object from the
response as a JSON file and pass it to `read-source`; the command rejects
unknown fields and requires the Artifact ID, revision ID and source digest.

```sh
woobe artifacts read-source WORKSPACE_ID --source-file ./source-ref.json \
  --offset 0 --max-chars 8000 --output compact
```

Upload streams a regular local file in server-bounded parts. The default private
checkpoint is stored under the CLI configuration directory; `--checkpoint`
selects a different private path. It records the source digest, target identity,
stable operation ID and acknowledged offset, never a credential. Resume checks
that the Project and API origin still match, revalidates the same local source,
and reconciles the remote offset before sending more bytes. If the initial
request or a part acknowledgement is lost, resume uses the original operation
ID and does not blindly replay bytes.

```sh
woobe artifacts upload WORKSPACE_ID --file ./invoice.pdf --path invoices/invoice.pdf
woobe artifacts upload resume --checkpoint ./upload-state.json
```

Replacing an existing Artifact requires both its ID and the exact current
revision ID, plus `--yes`. This is compare-and-swap; a stale revision is
rejected. `move`, `delete`, Workspace metadata changes and processing require
`--yes`; move/delete/update also require the expected catalog version where
applicable. Supply `--operation-id` for a mutation you may need to retry after
an uncertain response, and repeat the exact request with that same ID.

```sh
woobe artifacts upload WORKSPACE_ID --file ./invoice-v2.pdf \
  --path invoices/invoice.pdf --artifact-id ARTIFACT_ID \
  --expected-revision REVISION_ID --yes
woobe artifacts process WORKSPACE_ID ARTIFACT_ID REVISION_ID \
  --profile-id PROFILE_ID --profile-revision 4 --operation-id process-123 --yes
woobe artifacts move WORKSPACE_ID ARTIFACT_ID --path archive/invoice.pdf \
  --expected-version 9 --operation-id move-123 --yes
woobe artifacts delete WORKSPACE_ID ARTIFACT_ID --expected-version 10 \
  --operation-id delete-123 --yes
```

Downloads always name an immutable revision and stream into a private temporary
file beside the destination. The CLI publishes it only after size and SHA-256
verification. Existing files require `--yes`; without it, an existing file is
also protected against a concurrent create while the transfer is in progress.
Artifact bytes are never printed to normal command output.

```sh
woobe artifacts download WORKSPACE_ID ARTIFACT_ID REVISION_ID \
  --output-file ./invoice.pdf
```

See [output](OUTPUT.md), [pagination](PAGINATION.md) and the embedded skill's
[operations](../packages/woobe-cli-skill/skills/woobe-cli/references/operations.md)
and [recovery](../packages/woobe-cli-skill/skills/woobe-cli/references/recovery.md)
references for machine output and failure handling.
