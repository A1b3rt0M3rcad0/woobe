# Repository Refactoring Plan — AI

## Goals

1. Migrar de `BaseRepository` para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern A (Dual Inheritance)
3. Migrar `list_by_project` para `CursorPage`
4. Auditar `save()` e `update()` semantics
5. Outbox já existe — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `ProviderCredentialRepository` | `SQLAlchemyProviderCredentialRepository` | `ProviderCredentialModel` | `ProviderCredential` | Dual | — |
| `AgentRepository` | `SQLAlchemyAgentRepository` | `AgentModel` | `Agent` | Dual | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Dual Inheritance
Ambos usam `BaseRepository[Model], Interface`.

### List methods sem paginação (2 métodos)

| Repositório | Método | Retorno | Consumers |
|---|---|---|---|
| `ProviderCredentialRepository` | `list_by_project(project_id)` | `list[ProviderCredential]` | `ListCredentialsUseCase` |
| `AgentRepository` | `list_by_project(project_id)` | `list[Agent]` | `ListAgentsUseCase` |

### Save vs Update semantics
- `ProviderCredentialRepository.save()` = insert-only (`add` + `flush`)
- `AgentRepository.save()` = insert-only (`add` + `flush`)
- `AgentRepository.update(agent)` = carrega model por ID, modifica campos, `flush()` — **não usa `save()`**
- Isso é bom: separa `create` de `update` semanticamente

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 2 repositórios

### Task 2: Substituir chamadas para métodos protegidos
- [ ] `super().get_by_id(id)` → `await self._get_model_by_id(id)`
- [ ] `self.session.add(model)` → `await self._add_model(model)`
- [ ] `self.session.delete(model)` → `await self._delete_model(model)`
- [ ] `self.session.flush()` → `await self._flush()`

### Task 3: Migrar list methods para CursorPage (Option B)
- [ ] `ProviderCredentialRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[ProviderCredential]`
- [ ] `AgentRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[Agent]`

### Task 4: Auditar save semantics
- [ ] Documentar: `save()` = insert-only, `update()` = load-and-set (já separados)
- [ ] Manter sem mudanças

### Task 5: Padronizar flush/refresh
- [ ] `save()` atual: `flush()` apenas
- [ ] `update()` atual: `flush()` apenas
- [ ] Decisão: manter sem `refresh()` (entidades não têm campos gerados pelo banco além de `created_at`/`updated_at`)

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado com métodos protegidos
- [ ] `list_by_project` tem equivalente `paginate_by_project`
- [ ] `save()` vs `update()` semantics documentadas
- [ ] Outbox preservado
- [ ] Testes do AI passam
