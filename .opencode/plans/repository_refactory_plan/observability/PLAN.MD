# Repository Refactoring Plan — Observability

## Goals

1. Migrar de `BaseRepository` (Dual) para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern A (Dual Inheritance)
3. Migrar `list_by_project`, `list_by_session`, `list_by_trace` para `CursorPage`
4. Auditar `save()` semantics
5. Outbox já existe — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `TraceRepository` | `SQLAlchemyTraceRepository` | `TraceModel` | `Trace` | Dual | — |
| `TraceEventRepository` | `SQLAlchemyTraceEventRepository` | `TraceEventModel` | `TraceEvent` | Dual | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Dual Inheritance
Ambos usam `BaseRepository[Model], Interface`.

### Particularidades
- `SQLAlchemyTraceRepository.get_by_id()` chama `self.session.get()` diretamente (NÃO `super().get_by_id()`)
- `SQLAlchemyTraceRepository.delete()` também chama `self.session.get()` + `delete()` diretamente
- `SQLAlchemyTraceEventRepository.get_by_id()` chama `self.session.get()` diretamente
- `SQLAlchemyTraceEventRepository.delete()` chama `self.session.get()` + `delete()` diretamente

Isso significa que alguns métodos em `TraceRepository` e `TraceEventRepository` **não usam** o base. Precisamos padronizar.

### List methods com offset/limit (3 métodos)
Todos já usam `offset`/`limit` — boa prática.

| Repositório | Método | Retorno |
|---|---|---|
| `TraceRepository` | `list_by_project(project_id, limit, offset)` | `list[Trace]` |
| `TraceRepository` | `list_by_session(session_id, limit, offset)` | `list[Trace]` |
| `TraceEventRepository` | `list_by_trace(trace_id, limit, offset)` | `list[TraceEvent]` |

### Save semantics
- Ambos usam `save()` = insert-only (`add` + `flush` + `refresh`)
- Consistente e correto

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` em ambos repositórios

### Task 2: Substituir chamadas para métodos protegidos
- [ ] `self.session.get(TraceModel, id)` → `await self._get_model_by_id(id)` (TraceRepository)
- [ ] `self.session.get(TraceEventModel, id)` → `await self._get_model_by_id(id)` (TraceEventRepository)
- [ ] `self.session.add(model)` → `await self._add_model(model)`
- [ ] `self.session.delete(model)` → `await self._delete_model(model)`
- [ ] `self.session.flush()` → `await self._flush()`
- [ ] `self.session.refresh(model)` → `await self._refresh_model(model)`

### Task 3: Migrar list methods para CursorPage (Option B)
- [ ] `TraceRepository`: `paginate_by_project(...) -> CursorPage[Trace]`
- [ ] `TraceRepository`: `paginate_by_session(...) -> CursorPage[Trace]`
- [ ] `TraceEventRepository`: `paginate_by_trace(...) -> CursorPage[TraceEvent]`

### Task 4: Padronizar chamadas ao base
- [ ] Garantir que `TraceRepository.get_by_id()` e `delete()` usam `self._get_model_by_id()` em vez de `self.session.get()` direto

### Task 5: Preservar OutboxEventWriter
- [ ] Nenhuma mudança — `SQLAlchemyOutboxEventWriter` já segue o padrão

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado com métodos protegidos
- [ ] Todas as chamadas a `self.session.get()` substituídas por `self._get_model_by_id()`
- [ ] `list_by_*` têm equivalentes `paginate_by_*`
- [ ] Outbox preservado
- [ ] Testes do observability passam
