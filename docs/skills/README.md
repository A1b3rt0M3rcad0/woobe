# Agent Skills

Skills are reusable, versioned procedures owned by a Project. An Agent installs an exact version. Installation is independent from activation: the model initially receives compact discovery metadata, while instructions and text resources are loaded only when requested.

## Configure an Agent

Open **Build → Skills** in the Project sidebar, alongside Tools, Models and Credentials. **All Skills** lists the Project catalog with search, paging and version review. **Create Skill** provides name, usage description and instruction fields; **Import Skill** accepts `SKILL.md` or a package folder. Both publish immutable versions through the same server-validated catalog API.

**Installed on Agents** lists fixed versions in saved Agent configurations, including disabled bindings, with search by Skill or Agent and links to configure each Agent. It does not count unsaved edits or historical Releases as current installations. Loading and request failures are shown separately from empty results.

From a version, choose **Install on Agent**, select the Agent, then review the selected version in its Skills editor. Installation, version changes, enabling/disabling and removal are persisted with the editor’s existing **Save** flow. Importing/creating a catalog version happens immediately and does not itself install it on an Agent. Releasing and rolling back preserve pinned Skill versions and context policy.

Both the standalone Inspector and the Network Agent editor expose an explicit **Skills** tab. They use the same six-section navigation component, arranged in two rows so Skills remains visible in narrow panels. The old collapsed placement below the System Prompt was removed. Release details continue to show fixed versions and hashes.

The Project page is available at `/workspaces/:workspaceId/projects/:projectId/skills`; `/projects/:projectId/skills` uses the existing legacy redirect. Agent links use `?editor=skills`, optionally with `skill_version_id`, to open the requested version for review. Following a link never installs or saves a version implicitly.

Installation selects a registered Context Manager with `supports_skills`. The built-in implementation is the canonical **Standard Context Manager (`standard`)**. Historical `stdcm:v1`, `stdcm:v2`, and `default:v1` selections are read as `standard`; new snapshots persist only the stable unversioned identity. Enabled Skills cannot be saved with an incompatible manager or a policy that excludes SKILL or TOOL. Catalog browsing, creation and import remain available if manager metadata is unavailable; installation stays disabled until compatibility is known.

## Package contract

```markdown
---
name: invoice-review
description: Use when reviewing invoice totals before approval.
---
Check subtotal, taxes and the final amount. Consult references/checklist.md
when validating line items. Ask for clarification if required data is missing.
```

The YAML frontmatter requires a lowercase hyphenated `name` (up to 64 characters) and a `description` explaining when to use the Skill (up to 1024 characters). The body contains the procedure. Optional `license`, `compatibility` and `allowed-tools` metadata are retained; `allowed-tools` never grants permission.

This release supports Markdown/text instructions and up to 64 UTF-8 text resources under `references/` or `assets/` (`.md`, `.txt`, `.json`, `.yaml`, `.yml`, `.csv`). No arbitrary scripts, binaries, ZIP extraction, remote URL fetching or dependency installation occur. Unsupported files and path traversal are rejected. Limits: 1 MB per package, 200 KB per resource, 16 KB frontmatter; at most 1000 Agent bindings and 4 MB of package content per Agent snapshot. YAML aliases/anchors are rejected.

Version labels use `major.minor.patch` with an optional prerelease suffix. Published content is immutable: a new version must retain the same Skill name and use a new version label. The canonical package is hashed with SHA-256.

`required_tools` optionally declares the exact names exposed to the model that the procedure needs. Activation fails with the missing names if those Tools are not bound. Skill import/install never creates Tool bindings, bypasses permissions, resolves secrets or runs executable code.

## HTTP API

All operations are Project scoped and use the existing control-plane authentication and tenancy boundary:

| Method | Path | Behavior |
| --- | --- | --- |
| GET | `/ai/projects/{project_id}/skills` | Search names using `query`, `offset`, `limit` |
| POST | `/ai/projects/{project_id}/skills` | Create Skill and first version atomically |
| GET | `/ai/projects/{project_id}/skills/{skill_id}/versions` | List immutable version metadata |
| POST | `/ai/projects/{project_id}/skills/{skill_id}/versions` | Publish a new version |
| GET | `/ai/projects/{project_id}/skills/versions/{skill_version_id}` | Read a complete version |

Import body: `{ "version": "1.0.0", "skill_md": "...", "resources": {}, "required_tools": [] }`.

Agent `settings.runtime_config.skills` and Release `runtime_config.skills` contain:

```json
{
  "bindings": [{"skill_id": "uuid", "skill_version_id": "uuid", "enabled": true}],
  "snapshots": []
}
```

On Agent save, Release creation and Run acceptance, the server resolves explicit version ids in the owning Project, checks the package hash and replaces any client-supplied snapshot bytes. It does not resolve `latest`. Snapshots contain project, Skill, version ids, label, package hash and package bytes. The qualified `skill_version_id` avoids the existing prompt-version identifier in tenancy checks. No update/delete API is exposed for published packages.

## Runtime and Context Manager

Skills participate in the normal capability-enabled model invocation. There is no mandatory pre-inference applicability call and new Runs do not emit `skills_resolve(action="none")` when no Skill applies. The model receives the installed routing catalog and the current request together; it can answer directly or request a Skill operation.

The shared instrumented execution loop binds these internal operations when the Agent has enabled Skills:

- `skills_activate(skill_version_id)` loads complete instructions after checking installed membership and required Tools.
- `skills_read_resource(skill_version_id, path)` loads one resource from an already activated package.
- `skills_search(query, offset?)` is bound only when the installed routing catalog is incomplete. It discovers omitted installed names/descriptions and returns bounded, paginated metadata.

When a visible Skill applies, the model should call `skills_activate` directly with the exact installed `skill_version_id`; searching first is unnecessary. Activation runs after the model request that selected it, so the full procedural instructions become materialized in the next Model Invocation. Search results are metadata and do not activate a Skill. Resources are read only after activation and only when needed.

The runtime holds activation state per Run, shared by successive model invocations. The registry composes v2 with the existing standard assembler. The manager injects Skill contributions before history/current input with explicit provenance, avoiding duplicate instructions in Tool result history. Instructions are procedural guidance subordinate to Agent policy; references are user-level data. Activating/reading again returns a compact receipt without duplicating content.

`runtime_config.context.skills` defaults when Skills are installed:

```json
{"max_units": 8000, "catalog_max_units": 2000, "search_limit": 8}
```

These are estimates using Woobe's existing input-unit estimator, not exact provider token counts. If all routing metadata fits, the catalog is marked complete and `skills_search` is not exposed to the model. If it does not fit, the runtime preserves as many complete metadata entries as the configured catalog budget permits and records `installed_count`, `visible_count` and `omitted_count`; `skills_search` is then available only for omitted metadata. Descriptions are not truncated or summarized by another model. Full instructions and resources remain available until the Run ends, including terminal response and JSON repair invocations. A new Run starts with metadata again. No instruction content is automatically retained as Session history.

V2 preserves loaded instructions/resources in full. Activation that exceeds the Skills budget returns a failed operation without discarding previous instructions. If global mandatory context cannot fit the model budget, assembly fails explicitly. V2 does not summarize procedural instructions or promise unlimited active Skills. Token savings come from avoiding unused package bodies and from avoiding a mandatory Skill-resolution Model Invocation; repeated invocations still pay for content active in that Run.

Context Snapshots contain SKILL source units, hashes, version ids, resource paths, parent Tool call ids and selection methods, plus the Run retention manifest. Materialized text follows the existing references-only evidence policy. Normal Tool events expose activation/read/search receipts; Context Inspector displays the new source through its existing generic contribution view.

## Database and rollout

Migration `0064` creates `agent.skills` and `agent.skill_versions`, with Project/name and Skill/version uniqueness and an intra-Agent foreign key. No cross-module foreign key is added. Apply the migration before deploying API/workers that use Skills. No existing Agent is automatically migrated to v2.

For application rollback, first disable/remove Skills or restore a pre-Skills Agent/Network release. Keep the catalog tables while any historical snapshot may still use Skills. The migration has a downgrade that drops both tables; it is destructive and should only be used after packages are backed up and dependent bindings/releases are accounted for.

Browser validation, a real-provider smoke Run, and migration execution on PostgreSQL remain review/deployment checks when those environments are available. Local tests cover repository persistence using SQLite, PostgreSQL migration DDL, context assembly, real instrumented loops with a simulated model, Project authorization identifiers and editor serialization.

### Execution presentation

Standalone, Network and ChatSurface use the shared runtime client's Skill operation
presentation. `skills_search`, `skills_activate` and `skills_read_resource` are
shown as **Search Skills**, **Activate Skill** and **Read Skill resource**. Conversation
and Run evidence separate **Skill activity** from **Tool calls**; counts refer to
operations, not unique installed or activated Skills. Discovery is not activation.
A direct response that does not use a Skill creates no Skill activity.

Activation and resource receipts identify the Skill/version. Public completion events
and reattach projections retain that compact identity without instruction/resource
bodies. ChatSurface keeps Skill evidence beside the completed answer and restores it
from saved message evidence; its generic detail setting omits package names. Named
detail displays identity when available, including resumed Runs.

Transport event names and `tool_calls` fields remain compatible with existing
consumers and stored Runs. Historical `skills_resolve` records remain a reserved,
recognized presentation name so traces produced by older runtimes are still readable;
the operation is not bound or executable for new Runs. Aggregate diagnostics that do
not expose a breakdown are explicitly labelled **Tool/Skill operations**, including
their shared timing and context overhead. Raw protocol fields remain visible only as
technical evidence.
