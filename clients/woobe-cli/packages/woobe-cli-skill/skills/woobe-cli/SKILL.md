---
name: woobe-cli
description: 'Use Woobe CLI to inspect, create and edit Agents and Networks through local YAML, manage shared Providers, Models, Tools, Skills and Knowledge, import/export packages, run tests and operate staging, releases and production. Use when the user mentions Woobe, woobe-cli, .woobe-config, or Woobe Agent/Network development.'
compatibility: 'Requires woobe CLI 0.32.3 or newer. Remote operations require a compatible Woobe backend and a CLI Key saved in the selected connection.'
---

# Woobe CLI

Use this skill for Woobe operations. It guides the CLI; it is not a runtime Skill
uploaded to a Woobe Agent. Follow the user's scope and your host agent's approval
policy. Existing authorization does not require repeated confirmation.

## Start with the minimum evidence

1. Run `woobe version` and `woobe context show --output compact`.
2. Use `woobe agent list --fields "id,name,status" --output compact` or the exact
   resource getter when its UUID is known. Avoid full inventories and `--wide`.
3. For local development, use `woobe config check` and `woobe resources list`.
   An absent `.woobe-config` does not prevent ordinary API/runtime commands.
4. If authentication is absent, read [connection](references/connection.md).
   Never request, print or place CLI Keys in command arguments or author YAML.

## Choose the workflow

| Request | Read only this reference |
| --- | --- |
| Initialize a project, install/update assistant tooling | [setup](references/setup.md) |
| Connect, select Project, troubleshoot scope | [connection](references/connection.md) |
| Create/edit an Agent or Network with YAML | [development](references/development.md) |
| Providers/Models/Tools/Skills/Knowledge and shared dependencies | [dependencies](references/dependencies.md) |
| Declare configuration without secrets; inspect Environment status | [configuration](references/configuration.md) |
| Transfer portable packages between Projects | [packages](references/packages.md) |
| Unified deploy, delivery from Release/Staging/local and CI recovery | [deployment](references/deployment.md) |
| Tests, staging, release, production, rollback or archive | [lifecycle](references/lifecycle.md) |
| Runtime, administration, schemas, pagination or output | [operations](references/operations.md) |
| Missing files, incompatible backend, conflicts or uncertain writes | [recovery](references/recovery.md) |
| Offline signed receipts, pinned trust or key rotation/revocation | [signatures](references/signatures.md) |
| Origin locks, immutable local revisions and scoped history | [history](references/history.md) |

Prefer **pull → edit local YAML → validate/diff → push Draft** for an existing
Agent/Network. UUID, exact remote name, registered `@alias` and registered path
have different resolution rules; use UUID for unambiguous first pull. Do not
infer identity from a matching display name or create a second resource to edit
the first. Pull defaults to Draft. Push/import never promote automatically.

Consult the exact `COMMAND --help` or `woobe help "COMMAND" --output compact`
only when a flag/shape is uncertain. Discover the server DTO before composing
raw YAML input. Use `--output compact` and selected fields for inspection; use
JSON/JSONL only when structured processing needs it. Quote `--fields` lists in
PowerShell. Do not paste full schemas or package inventories into the chat.

Keep `.state/`, import checkpoints and pending receipts. Reconcile an uncertain
write before another attempt. Never blindly retry create/apply/publication.
Provider completion alone is not a passed output-contract test; consult lifecycle
and recovery for missing schema, invalid output and native test timeout UUIDs.
Only add `--yes` for the specifically authorized execution or lifecycle change.
State the affected connection, Project, resource and environment in your result,
then report verified changes and any unresolved server validation.
