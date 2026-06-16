# Cutover Checklist — Tools to Agent

## Pre-cutover (before spec 014)

- [ ] All tools domain contracts moved to agent (spec 005)
- [ ] All DTOs and use cases moved to agent (spec 006)
- [ ] Tool execution and secret resolution consolidated in agent (spec 007)
- [ ] Models, mappers, repositories integrated into AgentUnitOfWork (spec 008)
- [ ] Controllers, composers, schemas, routes moved to agent (spec 009)
- [ ] Events, Outbox, Inbox, workers consolidated (spec 010)
- [ ] Tools business tables migrated to agent schema (spec 011)
- [ ] Legacy Outbox/Inbox consolidated (spec 012)
- [ ] Imports, bootstrap, Alembic, DI updated (spec 013)

## Cutover execution (spec 014)

- [ ] Deploy code with shims enabled
- [ ] Verify legacy routes return same responses as new routes
- [ ] Monitor outbox processing for both legacy and agent outboxes
- [ ] Verify event routing: both old and new routing keys active
- [ ] Run smoke tests against both route sets
- [ ] Verify secret creation/retrieval works through agent code path
- [ ] Verify tool execution works through agent code path
- [ ] No errors in application logs during shim period

## Post-cutover (spec 014+)

- [ ] Remove legacy route shims after validation period
- [ ] Remove legacy worker registrations
- [ ] Remove importlib-based adapters (ToolsToolExecutor, ToolsToolRepository)
- [ ] Update test references from `modules.tools` to `modules.agent`

## Go/No-go gates

| Gate | Criteria |
|---|---|
| Pre-spec-011 | tools.outbox_events count == 0 (no pending events) |
| Pre-spec-012 | Both legacy and new outboxes process events identically |
| Pre-spec-016 | No production code imports `modules.tools` (confirmed via grep) |

## Monitoring during cutover

- Application error rate
- Outbox processing latency
- Tool execution success/failure rate
- Secret operation success/failure rate
- HTTP route response correctness (/tools vs /agent/tools)
