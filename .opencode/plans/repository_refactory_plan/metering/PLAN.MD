# Repository Refactoring Plan — Metering

## Goals

1. Migrar `SQLAlchemyUsageEventRepository` de `BaseRepository` (Dual) para `BaseSQLAlchemyRepository` (protegido)
2. `SQLAlchemyUsageDailyProjectRepository` e `SQLAlchemyUsageDailyAgentRepository` não herdam de `BaseRepository` — verificar pattern atual
3. Migrar `list_by_project` e `list_by_agent` para `CursorPage`
4. Auditar `save()` semantics (incluindo `session.merge()`)
5. Outbox já existe — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `UsageEventRepository` | `SQLAlchemyUsageEventRepository` | `UsageEventModel` | `UsageEvent` | Dual | — |
| `UsageDailyProjectRepository` | `SQLAlchemyUsageDailyProjectRepository` | `UsageDailyProjectModel` | `UsageDailyProject` | Nenhum | — |
| `UsageDailyAgentRepository` | `SQLAlchemyUsageDailyAgentRepository` | `UsageDailyAgentModel` | `UsageDailyAgent` | Nenhum | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Misto
- `SQLAlchemyUsageEventRepository`: Dual Inheritance (`BaseRepository[UsageEventModel], UsageEventRepository`)
- `SQLAlchemyUsageDailyProjectRepository`: **NÃO herda de BaseRepository** — só tem `self.session`
- `SQLAlchemyUsageDailyAgentRepository`: **NÃO herda de BaseRepository** — só tem `self.session`

### List methods com offset/limit (3 métodos)
Os 3 já usam `offset`/`limit` — boa prática, mas não é cursor-based.

| Repositório | Método | Retorno |
|---|---|---|
| `UsageEventRepository` | `list_by_project(project_id, limit, offset)` | `list[UsageEvent]` |
| `UsageDailyProjectRepository` | `list_by_project(project_id, limit, offset)` | `list[UsageDailyProject]` |
| `UsageDailyAgentRepository` | `list_by_agent(agent_id, limit, offset)` | `list[UsageDailyAgent]` |

### Save semantics — ponto de atenção
- `UsageEventRepository.save()` = insert-only (`add` + `flush` + `refresh`)
- `UsageDailyProjectRepository.save()` = **`session.merge(model)`** — upsert!
- `UsageDailyAgentRepository.save()` = **`session.merge(model)`** — upsert!

Isso é intencional: tabelas de daily aggregate usam PK composta (`project_id + day`). `merge()` é a estratégia correta aqui.

### Outros métodos
- `UsageEventRepository.get_by_id()` chama `self.session.get()` diretamente (não `super().get_by_id()`)
- `UsageEventRepository.delete()` chama `self.session.get()` + `delete()` diretamente
- `UsageDailyProjectRepository` e `UsageDailyAgentRepository`: sem `get_by_id`, `delete`

## Tasks

### Task 1: Atualizar SQLAlchemyUsageEventRepository para BaseSQLAlchemyRepository
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository`
- [ ] `super().get_by_id(id)` → `await self._get_model_by_id(id)`
- [ ] `self.session.add(model)` → `await self._add_model(model)`
- [ ] `self.session.delete(model)` → `await self._delete_model(model)`
- [ ] `self.session.flush()` → `await self._flush()`
- [ ] `self.session.refresh(model)` → `await self._refresh_model(model)`

### Task 2: Decidir pattern para UsageDaily* repositories
- [ ] Opção A: Fazer herdar de `BaseSQLAlchemyRepository`
- [ ] Opção B: Manter sem herança (só `self.session`) — já que usam `merge()` e não `add()`
- [ ] Decisão recomendada: **Opção B** — `merge()` foge do padrão `_add_model`. Manter composition manual.

### Task 3: Migrar list methods para CursorPage (Option B)
- [ ] `UsageEventRepository`: adicionar `paginate_by_project(...) -> CursorPage[UsageEvent]`
- [ ] `UsageDailyProjectRepository`: adicionar `paginate_by_project(...) -> CursorPage[UsageDailyProject]`
- [ ] `UsageDailyAgentRepository`: adicionar `paginate_by_agent(...) -> CursorPage[UsageDailyAgent]`

### Task 4: Preservar merge semantics
- [ ] Documentar: `UsageDaily*.save()` usa `session.merge()` — upsert intencional para agregados diários
- [ ] NÃO mudar para `add()`

### Task 5: Preservar OutboxEventWriter
- [ ] Nenhuma mudança — `SQLAlchemyOutboxEventWriter` já segue o padrão

## Acceptance Criteria

- [ ] `SQLAlchemyUsageEventRepository` usa `BaseSQLAlchemyRepository` com métodos protegidos
- [ ] `UsageDaily*` repositories mantêm merge semantics
- [ ] `list_by_*` têm equivalentes `paginate_by_*`
- [ ] Merge semantics documentadas
- [ ] Outbox preservado
- [ ] Testes do metering passam
