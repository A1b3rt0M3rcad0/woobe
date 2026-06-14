---
name: projectrai-discovery-inventory
description: Build ProjectRAI migration inventories for files, imports, database ownership, routes, events, workers, and risks before moving code.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: discovery
  scope: inventory
---

# ProjectRAI Discovery Inventory

Use this skill for specs `003` through `009`, or whenever the user asks OpenCode to map the current ProjectRAI repository before implementing the `agent` migration.

This skill exists to prevent blind refactors. The specs require objective inventories before physical movement of code, database ownership changes, worker rewiring, or legacy removal.

## Required inventories

Create or update files under `/specs/execution/inventory/` as required by the active spec:

- `files.md`: repository file inventory, especially `src/modules/ai`, `src/modules/knowledge`, `src/modules/runtime`, `src/workers`, `src/shared/workers`, tests, migrations, and bootstrap files.
- `imports.md`: import dependency map, with explicit cross-module imports and forbidden internal imports.
- `database-ownership.md`: schemas, tables, SQLAlchemy models, migrations, Foreign Keys, ownership, and cross-module constraints.
- `routes.md`: API route map, routers registered by `src/main.py`, legacy public endpoints, target `/agent` routes, and shim requirements.
- `events.md`: event types, producers, consumers, routing keys, queue names, Outbox/Inbox tables, event envelope variants, and versioning.
- `workers.md`: root workers, shared worker infrastructure, concrete module workers, runner behavior, registries, handlers, queues, and business logic leakage.
- `risks.md` or equivalent risk register: migration risks, severity, evidence, mitigation, owner/spec, and unblock criteria.

## Discovery commands

Start with safe read-only commands. Prefer `rg`, `find`, Python AST parsing, and SQLAlchemy/migration static inspection before runtime execution.

Useful commands:

```bash
pwd
git status --short
git branch --show-current
find src -maxdepth 5 -type f | sort
find tests -maxdepth 6 -type f | sort || true
find migrations -maxdepth 4 -type f | sort || true
rg "from modules\.(ai|knowledge|runtime)|import modules\.(ai|knowledge|runtime)" src tests || true
rg "from modules\.[a-z_]+\.(domain|application|service|infra|presentation)" src tests || true
rg "ForeignKey|op\.create_foreign_key|FOREIGN KEY|__table_args__|schema=" src migrations tests || true
rg "APIRouter|include_router|router|prefix=" src/modules src/main.py || true
rg "Outbox|Inbox|Rabbit|routing_key|event_type|Consumer|Dispatcher|Worker|UnitOfWork|PostgresUnitOfWork" src tests || true
```

When repository conventions differ from the spec assumptions, document the difference as an inconsistency. Do not silently normalize or rename.

## Inventory quality rules

Each inventory item must include:

- Current file path.
- Module or layer owner.
- Observed dependency or responsibility.
- Whether it is allowed, forbidden, legacy-temporary, or unknown.
- Evidence command or static reference.
- Migration implication.

For `imports.md`, classify imports as:

- Same module: allowed.
- Public contract import: potentially allowed if explicitly designed as public API.
- Internal cross-module import: forbidden unless allowlisted by a spec.
- Legacy `ai`/`knowledge`/`runtime` import: allowed only during migration and must have a removal path.

For `database-ownership.md`, classify each table/constraint as:

- Same-module ownership.
- Legacy ownership to be migrated into `agent`.
- Cross-module FK violation.
- Opaque external id reference without constraint.
- Unknown ownership requiring manual decision.

## Risk register rules

Do not create vague risks. A valid risk entry needs:

- ID.
- Description.
- Evidence.
- Affected specs.
- Severity.
- Probability.
- Mitigation.
- Unblock or close condition.

Typical high-risk items in this project:

- Cross-module Unit of Work in runtime ask flow.
- Global workers containing business event handling.
- Shared worker infrastructure with hard-coded module lists.
- RabbitMQ queue topology coupled to old module names.
- Alembic metadata importing legacy modules directly.
- Physical Foreign Keys across schemas.
- Legacy route compatibility without shim tests.

## Completion criteria

Do not mark discovery specs complete unless inventories are actually written, runtime status is updated, and inconsistencies/blockers are explicit.

A discovery result is allowed to say `unknown`, but only with evidence of what was checked and what remains unresolved.
