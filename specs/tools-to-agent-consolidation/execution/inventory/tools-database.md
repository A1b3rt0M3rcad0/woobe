# Tools Module — Database Inventory

Schema: `tools`

## Tables

### `tools.tools`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, default gen_random_uuid() |
| project_id | UUID | **FK -> core.projects.id** (cross-schema) |
| agent_id | UUID | nullable, no FK |
| name | String(255) | NOT NULL |
| description | Text | nullable |
| type | String(64) | NOT NULL |
| config | JSONB | nullable |
| input_schema | JSONB | nullable |
| output_schema | JSONB | nullable |
| risk_level | String(32) | default 'low' |
| timeout_ms | Integer | nullable |
| status | String(32) | default 'active' |
| created_at | Timestamp | auto |
| updated_at | Timestamp | auto |

### `tools.secrets`

| Column | Type | Constraints |
|---|---|---|
| id | UUID | PK, default gen_random_uuid() |
| project_id | UUID | **FK -> core.projects.id** (cross-schema) |
| name | String(255) | NOT NULL |
| type | String(64) | NOT NULL |
| encrypted_value | Text | NOT NULL |
| data | JSONB | nullable |
| created_at | Timestamp | auto |
| updated_at | Timestamp | auto |

Unique: (`project_id`, `name`)

### `tools.outbox_events`

Base columns inherited from `shared.infra.database.outbox.OutboxEventModel`.

### `tools.inbox_events`

Base columns inherited from `shared.infra.database.inbox.InboxEventModel`.

## Cross-module Foreign Keys

| Source | Target | Issue |
|---|---|---|
| `tools.tools.project_id` | `core.projects.id` | Cross-schema FK — must be removed (migrate to opaque UUID with index) |
| `tools.secrets.project_id` | `core.projects.id` | Cross-schema FK — must be removed (migrate to opaque UUID with index) |

## Internal Foreign Keys (within `agent` schema — allowed after migration)

None currently (agent_id is UUID without FK).

## Migration evidence

From `migrations/versions/0002_create_all_tables.py`:
- Lines referencing `schema="tools"`: 518 (tools), 533 (secrets), 553 (outbox_events), 574 (inbox_events)
- Drop operations at lines 891-894 reference `schema="tools"` tables

From `migrations/versions/0012_make_tool_agent_id_nullable.py`:
- Lines 22, 32: references `schema="tools"`

## Summary

- **4 tables** in `tools` schema
- **2 cross-schema FKs** pointing to `core.projects` — must be replaced with opaque UUIDs
- **1 unique constraint** across `tools.secrets`
- **0 internal FKs** within tools schema
- Outbox/Inbox tables inherit from shared base models

Executed: static inspection of `src/modules/tools/infra/database/models.py`, `migrations/versions/0002_create_all_tables.py`, `migrations/versions/0012_make_tool_agent_id_nullable.py`
Exit code: 0
