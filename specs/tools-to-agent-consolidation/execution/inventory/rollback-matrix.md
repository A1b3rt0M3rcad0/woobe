# Rollback Matrix — Tools to Agent

## Code rollback

| Scenario | Action | Data loss | Risk |
|---|---|---|---|
| Spec 005-009 fails (domain/application move) | Revert moved files via `git revert` or `git checkout` | None (additive only, no code removed) | Low |
| Spec 010 fails (events/workers) | Revert event type changes, restore legacy routing | May lose in-flight events; drain queues first | Medium |
| Spec 011 fails (table migration) | Run downgrade migration before contract phase; keep tools schema | None if downgrade before DROP | Low |
| Spec 012 fails (legacy outbox/inbox merge) | Restore legacy outbox tables, re-point workers | Pending events may be duplicated; idempotency key dedup | Medium |
| Spec 013 fails (imports/bootstrap) | Revert import changes, restore legacy bootstrap | None | Low |
| Spec 014 fails (cutover) | Restore legacy route registration, disable agent routes | Brief HTTP 503 for in-flight requests | Medium |
| Spec 015 fails (tests) | Fix tests, no rollback needed | None | Low |
| Spec 016 fails (remove module) | **NOT POSSIBLE** after DROP SCHEMA | Full tool data loss | Critical |

## Database rollback

| Migration | Downgrade target | Preserves data? | Notes |
|---|---|---|---|
| Tools tables SET SCHEMA → agent | `0020 (head)` → run reverse SET SCHEMA to tools | Yes | Must happen before DROP SCHEMA |
| FK removal | Re-add FK constraints | Yes | Validate no orphaned rows first |
| Outbox/Inbox consolidation | Restore tools.outbox_events, tools.inbox_events | Yes | May have duplicate rows; dedup by idempotency_key |
| DROP SCHEMA tools | Cannot downgrade | **No** | Run only after go/no-go approval |

## Event rollback

| Scenario | Action | Risk |
|---|---|---|
| tools.tool.* events change to agent.tool.* | Revert event type mapping; reconfigure RabbitMQ bindings | In-flight messages misrouted; drain queues first |
| RabbitMQ queue name changes | Restore old queue bindings | Messages may queue in old queues |

## Rollback commands

```bash
# Code rollback (pre-commit)
git checkout -- path/to/file.py

# Code rollback (post-commit but before next spec commit)
git revert HEAD

# Migration rollback (pre-contract)
alembic downgrade -1

# Full migration rollback to pre-tools-migration state
alembic downgrade 0020
```

## Rollback approval

Specs 011, 012, and 016 require explicit go/no-go approval before execution:

- **Spec 011** (table migration): Requires confirmed zero pending events in legacy outbox
- **Spec 012** (outbox/inbox consolidation): Requires confirmed dual-write parity
- **Spec 016** (remove module): Requires confirmed no production references to `modules.tools`
