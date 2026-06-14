---
name: projectrai-database-migrations
description: Implement ProjectRAI SQLAlchemy and Alembic migrations for agent ownership, Outbox/Inbox, UoW, expand-migrate-contract, and cross-module FK removal.
license: MIT
compatibility: opencode
metadata:
  project: ProjectRAI
  phase: database
  scope: sqlalchemy-alembic
---

# ProjectRAI Database and Migration Discipline

Use this skill for specs `005`, `070` through `079`, `100` through `105` when database state is involved, `134`, and final validation of database boundaries.

The database rule is strict: each module owns its own schema/tables and transaction boundary. The final architecture must not contain physical Foreign Keys across modules. External ids may be stored as opaque scalar references only.

## Ownership rules

Allowed Foreign Keys:

- `agent.*` to `agent.*`
- `billing.*` to `billing.*`
- `metering.*` to `metering.*`
- `identity.*` to `identity.*`
- Same-module constraints only

Forbidden Foreign Keys:

- `agent.*` to `billing`, `metering`, `identity`, `core`, `tools`, or `observability`
- Any module to `agent.*` unless it is within the same module ownership boundary
- Any final FK to `ai`, `knowledge`, or `runtime`
- Alembic `op.create_foreign_key` across module schemas
- Raw SQL `FOREIGN KEY` constraints across module schemas

Opaque references are allowed:

```python
customer_id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
```

Cross-module physical constraints are not allowed:

```python
ForeignKey("identity.users.id")
op.create_foreign_key(..., source_schema="agent", referent_schema="identity")
```

## Expand-migrate-contract

Use expand-migrate-contract for destructive or ownership-changing migrations:

1. Expand: add new `agent` structures without dropping legacy structures.
2. Migrate: backfill/copy data with deterministic, repeatable scripts or migrations.
3. Dual-read or shim only when explicitly required by the spec.
4. Contract: remove old structures only in the later deprecation/removal specs.

Do not rename or drop legacy tables in an early migration. Do not remove `ai`, `knowledge`, or `runtime` schemas before the active cleanup specs allow it.

## Agent Outbox model expectations

The agent outbox table should be in `agent.outbox_events` or the active spec's exact name. Expected fields include:

- `id UUID PK`
- `aggregate_type`
- `aggregate_id`
- `event_type`
- `event_version`
- `routing_key`
- `payload JSONB`
- `metadata JSONB`
- `idempotency_key`
- `correlation_id`
- `causation_id`
- `status`
- `attempts`
- `available_at`
- `locked_at`
- `locked_by`
- `published_at`
- `error`
- `created_at`
- `updated_at`

Required indexes/constraints typically include unique `idempotency_key`, pending/retryable claim index, correlation index, and aggregate index.

## Agent Inbox model expectations

The agent inbox table should support durable receive, idempotent processing, retries, and dead-letter classification. It should include event identity, producer, event type/version, payload, metadata, status, attempts, available/locked fields, processed/dead timestamps, error, and correlation/causation fields.

## Unit of Work rules

`AgentUnitOfWork` may coordinate only agent-owned repositories, `agent` Outbox, and `agent` Inbox in one transaction. It must not include repositories from `billing`, `metering`, `identity`, `observability`, `tools`, `core`, or legacy `ai`/`knowledge`/`runtime` after migration.

A cross-module side effect must be represented by an Outbox event and consumed by the other module's Inbox.

## Alembic discipline

Before editing migrations:

```bash
find migrations -maxdepth 4 -type f | sort
rg "ai|knowledge|runtime|agent|ForeignKey|op\.create_foreign_key|FOREIGN KEY|metadata" migrations src/modules || true
```

When creating migrations:

- Use deterministic revision naming.
- Include schema creation when needed.
- Avoid importing legacy models for final metadata.
- Ensure upgrade and downgrade are valid in a test database.
- Do not depend on production data shape not documented in the inventory.
- Preserve rollback path for the current spec.

## Database boundary tests

Implement or update tests that detect:

- SQLAlchemy `ForeignKey("schema.table.column")` cross-module references.
- `sa.ForeignKey` and `mapped_column(ForeignKey(...))` variants.
- Alembic `op.create_foreign_key` cross-module references.
- Raw SQL `FOREIGN KEY` constraints.
- Final allowlist not empty.
- FKs to `ai`, `knowledge`, or `runtime` after cleanup.

Final validation should include a PostgreSQL `pg_constraint` query classifying every remaining FK as `same_module`. Store the final output in the report path required by the spec, commonly `/specs/execution/final-database-constraints.md`.

## Validation commands

Use the commands required by the active spec when available:

```bash
ruff check src tests
pytest tests/architecture/test_database_boundaries.py
pytest tests/modules/agent
alembic upgrade head
alembic downgrade -1
alembic upgrade head
rg "ForeignKey\(.*(ai|knowledge|runtime|billing|metering|identity|core|tools|observability)\." src/modules migrations tests || true
rg "op\.create_foreign_key|FOREIGN KEY" migrations src/modules || true
```

If Alembic is not configured or no test database is available, mark the spec blocked or partially complete only with explicit runtime evidence. Do not claim migration safety without upgrade/downgrade evidence.
