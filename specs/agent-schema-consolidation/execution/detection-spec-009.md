# Detection Results — Spec 009

## Guard checks

| Check | Status | Exit code |
|---|---|---|
| Branch is `development_agent-schema-consolidation` | PASS | 0 |
| Baseline `537e401` is ancestor of HEAD | PASS | 0 |
| Working tree clean | PASS | - |
| HEAD SHA | `0b738d8` | - |

## Detection commands

| Comando | Exit code | Notas |
|---|---|---|
| `Select-String legacy schema refs in models.py` | 0 | 6 legacy refs remain (all in messaging classes: Outbox/InboxEventModel variants) |
| `Select-String ForeignKey("ai.|knowledge.|runtime.")` in models.py | 0 | No legacy ForeignKey refs remain; all changed to `agent.*` intra-agent FKs |
| `alembic heads` | 0 | `0017 (head)` |

## Changes applied

### models.py — schema references (15 business tables → agent)

| Table class | Old schema | New schema |
|---|---|---|
| ProviderCredentialModel | ai | agent |
| AgentModel | ai | agent |
| AgentPromptModel | ai | agent |
| AgentContractModel | ai | agent |
| AgentModelConfigModel | ai | agent |
| AgentReleaseModel | ai | agent |
| AgentReleaseTestModel | ai | agent |
| DocumentCollectionModel | knowledge | agent |
| AgentCollectionModel | knowledge | agent |
| DocumentModel | knowledge | agent |
| DocumentChunkModel | knowledge | agent |
| KnowledgeVersionModel | knowledge | agent |
| SessionModel | runtime | agent |
| MessageModel | runtime | agent |
| AskJobModel | runtime | agent |

### models.py — legacy messaging classes (kept as-is, spec 011)

| Class | Schema | Reason |
|---|---|---|
| OutboxEventModel | ai | Legacy outbox — spec 011 |
| InboxEventModel | ai | Legacy inbox — spec 011 |
| KnowledgeOutboxEventModel | knowledge | Legacy outbox — spec 011 |
| KnowledgeInboxEventModel | knowledge | Legacy inbox — spec 011 |
| RuntimeOutboxEventModel | runtime | Legacy outbox — spec 011 |
| RuntimeInboxEventModel | runtime | Legacy inbox — spec 011 |

### models.py — ForeignKey changes (all intra-agent → agent.*)

All legacy-schema FK references in agent models.py changed from `ForeignKey("ai|knowledge|runtime.<table>.id")` to `ForeignKey("agent.<table>.id")`. Cross-module FKs (`core.projects.id`, `identity.users.id`) remain unchanged.

### Allowlist — models.py entries removed

All 6 entries with `removal_spec: "009"` removed from `legacy_schema_allowlist.yaml`. Cross-module FK entries (metering, observability, tools) kept (`removal_spec: "010"`). Migration history entries kept (`removal_spec: "016"`).

### AGENT_TABLE_SCHEMAS — updated

In `test_spec_004_schema_guards.py` and `preflight.py`, all 15 business tables now map to `schema="agent"`.

## Pendências

- Cross-module FKs (`core.projects.id`, `identity.users.id`) remain — removidos na spec 010.
- Legacy messaging classes mantêm schemas antigos → resolvido na spec 011.
