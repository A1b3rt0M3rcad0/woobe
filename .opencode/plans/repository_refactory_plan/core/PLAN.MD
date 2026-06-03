# Repository Refactoring Plan — Core

## Goals

1. Migrar de `BaseRepository` para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern A (Dual Inheritance)
3. Migrar `list_by_organization` e `list_by_project` para `CursorPage`
4. Auditar `save()` semantics (insert-only)
5. Outbox já existe — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `ProjectRepository` | `SQLAlchemyProjectRepository` | `ProjectModel` | `Project` | Dual | — |
| `ApiKeyRepository` | `SQLAlchemyApiKeyRepository` | `ApiKeyModel` | `ApiKey` | Dual | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Dual Inheritance
Ambos repositórios usam `BaseRepository[Model], Interface`.

### List methods sem paginação (2 métodos)

| Repositório | Método | Retorno | Consumers |
|---|---|---|---|
| `ProjectRepository` | `list_by_organization(org_id)` | `list[Project]` | `ListProjectsUseCase` |
| `ApiKeyRepository` | `list_by_project(project_id)` | `list[ApiKey]` | `ListApiKeysUseCase` |

### Save semantics
- `save()` em ambos = insert-only (`self.session.add()` + `flush()`)
- Sem `refresh()` após `flush()`
- Sem `update()` explícito — se precisar atualizar, usa-se `save()` novamente com merge implícito? Risco.

### Outbox
✅ `SQLAlchemyOutboxEventWriter` implementado corretamente

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository
- [x] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 2 repositórios

### Task 2: Substituir chamadas para métodos protegidos
- [x] `super().get_by_id(id)` → `await self._get_model_by_id(id)`
- [x] `self.session.add(model)` → `await self._add_model(model)`
- [x] `self.session.delete(model)` → `await self._delete_model(model)`
- [x] `self.session.flush()` → `await self._flush()`

### Task 3: Padronizar flush + refresh
- [x] Adicionar `refresh()` após `flush()` em ambos `save()` para consistência

### Task 4: Auditar `save()` semantics
- [x] `save()` é insert-only — não há chamadas de update nos repositórios core
- [x] Mantido como insert-only padronizado com flush+refresh

### Task 5: Migrar list methods para CursorPage (Option B)
- [x] `ProjectRepository`: adicionar `paginate_by_organization(org_id, *, limit, cursor) -> CursorPage[Project]`
- [x] `ApiKeyRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[ApiKey]`
- [x] Atualizar interfaces de domínio com novos métodos paginados

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado com métodos protegidos
- [ ] `list_by_organization` e `list_by_project` têm equivalentes `paginate_by_*`
- [ ] `save()` semantics auditadas — decisão documentada
- [ ] `flush()` + `refresh()` padronizado
- [ ] Outbox preservado
- [ ] Testes do core passam
