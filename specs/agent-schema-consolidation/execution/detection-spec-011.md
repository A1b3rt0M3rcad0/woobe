# Detection Evidence — Spec 011

## Guard checks

| Check | Result |
|---|---|
| Branch | `development_agent-schema-consolidation` ✅ |
| Baseline SHA ancestor | `537e401` is ancestor of HEAD ✅ |
| Working tree clean before changes | Clean ✅ |
| HEAD before changes | `acb3009e297a6ff3e11013b9b2758922cc546e58` |

## Detection commands

### `alembic heads`
- Exit code: 0
- Result: `0018 (head)`

### `alembic current`
- Exit code: 1
- Result: `ConnectionResetError` / `ConnectionDoesNotExistError`
- Pendência: PostgreSQL não está disponível neste ambiente.

### `Select-String` — legacy schema refs in models.py
Matched 6 legacy schema references:
- `models.py:73` — `"schema": "ai"` (OutboxEventModel)
- `models.py:78` — `"schema": "ai"` (InboxEventModel)
- `models.py:281` — `"schema": "knowledge"` (KnowledgeOutboxEventModel)
- `models.py:286` — `"schema": "knowledge"` (KnowledgeInboxEventModel)
- `models.py:340` — `"schema": "runtime"` (RuntimeOutboxEventModel)
- `models.py:345` — `"schema": "runtime"` (RuntimeInboxEventModel)

Plus 2 legacy imports in models.py:
- Line 25: `from shared.infra.database.inbox import InboxEventModel as BaseInbox`
- Line 26: `from shared.infra.database.outbox import OutboxEventModel as BaseOutbox`

### `Select-String` — legacy writer refs in repositories.py
- `repositories.py:99` — `KnowledgeOutboxEventModel` import
- `repositories.py:104` — `RuntimeOutboxEventModel` import
- `repositories.py:107` — `OutboxEventWriter` import
- `repositories.py:252` — `class SQLAlchemyOutboxEventWriter`
- `repositories.py:1003` — `class SQLAlchemyKnowledgeOutboxEventWriter`
- `repositories.py:1207` — `class SQLAlchemyRuntimeOutboxEventWriter`

### `Select-String` — legacy refs in preflight.py
- Lines 32-37: `_LEGACY_OUTBOX_TABLES` list (6 entries)
- Line 139: `"outbox_events", "inbox_events"` exclusion in `check_target_table_conflicts`

### `Select-String` — legacy messaging in test_spec_009_agent_models.py
- Lines 32-38: `LEGACY_MESSAGING_TABLES` with 6 entries
- Line 66: `test_legacy_messaging_tables_keep_schemas` test

### External composer imports
9 composer files import legacy writers:
- `ask_agent_composer.py` — `SQLAlchemyRuntimeOutboxEventWriter`
- `create_agent_composer.py` — `SQLAlchemyOutboxEventWriter`
- `create_collection_composer.py` — `SQLAlchemyKnowledgeOutboxEventWriter`
- `create_provider_credential_composer.py` — `SQLAlchemyOutboxEventWriter`
- `create_session_composer.py` — `SQLAlchemyRuntimeOutboxEventWriter`
- `send_message_composer.py` — `SQLAlchemyRuntimeOutboxEventWriter`
- `update_agent_composer.py` — `SQLAlchemyOutboxEventWriter`
- `update_provider_credential_composer.py` — `SQLAlchemyOutboxEventWriter`
- `upload_document_composer.py` — `SQLAlchemyKnowledgeOutboxEventWriter`

## Pendências

- `alembic current` não executável (sem PostgreSQL).
- Migration 0019 não executada (sem PostgreSQL).
- Dados em tabelas legadas não verificáveis (sem PostgreSQL).
