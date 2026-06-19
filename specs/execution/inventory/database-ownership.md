# Current database ownership map

- Identity schema: models in `src/modules/identity/infra/database/models.py` use `schema = identity`.
- `identity.users` owns user credentials and lifecycle state.
- `identity.organizations` and membership tables own tenant membership.
- `identity.user_sessions` owns hashed refresh sessions and replacement lineage.
- Core schema: models in `src/modules/core/infra/database/models.py` own projects and project API keys.
- Agent schema: models in `src/modules/agent/infra/database/models.py` own agents, provider credentials and releases.
- Agent schema also owns tools, encrypted tool secrets, knowledge collections, documents and chunks.
- Agent schema owns runtime sessions, messages and async ask jobs.
- Observability schema: models in `src/modules/observability/infra/database/models.py` own traces and trace events.
- Metering schema: models in `src/modules/metering/infra/database/models.py` own usage projections.
- Billing schema: models in `src/modules/billing/infra/database/models.py` own billing projections.
- Each persisted module has canonical InboxEvent and OutboxEvent tables or shared canonical equivalents.
- Cross-module ForeignKey usage is limited to stable aggregate identifiers and explicit ownership contracts.
- `migrations/versions/` is the authoritative schema evolution chain.
- Migration `0029_link_rotated_user_sessions.py` adds the refresh-session self ForeignKey.
- Current schema correctness is checked with empty-database upgrade and Alembic drift detection.
- SQLAlchemy `__tablename__` and schema declarations are reviewed by integration tests.
