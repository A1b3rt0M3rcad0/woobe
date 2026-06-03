# Repository Refactoring Plan — Tools

## Goals

1. Migrar de `BaseRepository` (Composition) para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern B (Composition) — não mudar para herança
3. Migrar `list_by_project`, `list_by_agent` para `CursorPage`
4. Auditar `create()`, `update()` semantics
5. Adicionar `SQLAlchemyOutboxEventWriter` (atualmente ausente)

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `ToolRepository` | `SQLAlchemyToolRepository` | `ToolModel` | `Tool` | Composition | ❌ |
| `SecretRepository` | `SQLAlchemySecretRepository` | `SecretModel` | `Secret` | Composition | ❌ |

## Diagnosis

### Pattern: Composition
Ambos usam `self._base = BaseRepository(session, Model)`.

### List methods sem paginação (4 métodos)

| Repositório | Método | Retorno | Consumers |
|---|---|---|---|
| `ToolRepository` | `list_by_project(project_id)` | `list[Tool]` | `ListToolsUseCase` |
| `ToolRepository` | `list_by_agent(agent_id)` | `list[Tool]` | `ListAgentToolsUseCase` |
| `SecretRepository` | `list_by_project(project_id)` | `list[Secret]` | `ListSecretsUseCase` |

### Create semantics
- `create()` em ambos = insert-only (`self.session.add(model)` + `flush()` + `refresh()`)
- Consistente

### Update semantics
- `update()` em ambos = load-and-set fields
- Ambos levantam `ToolNotFoundError`/`SecretNotFoundError` se não encontrar

### Delete semantics
- `delete(id)` = load + delete, levanta `ToolNotFoundError`/`SecretNotFoundError`

### Outbox
❌ Nenhum dos 2 repositórios tem `SQLAlchemyOutboxEventWriter`.

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository na composição
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 2 repositórios
- [ ] `self._base = BaseSQLAlchemyRepository(session, Model)`

### Task 2: Substituir chamadas para métodos protegidos
- [ ] `self._base.get_by_id(id)` → `await self._base._get_model_by_id(id)`
- [ ] `self._base.delete(model)` → `await self._base._delete_model(model)`
- [ ] `self.session.add(model)` → `await self._base._add_model(model)` (nos `create()`)
- [ ] `self.session.flush()` → `await self._base._flush()`
- [ ] `self.session.refresh(model)` → `await self._base._refresh_model(model)`

### Task 3: Migrar list methods para CursorPage (Option B)
- [ ] `ToolRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[Tool]`
- [ ] `ToolRepository`: adicionar `paginate_by_agent(agent_id, *, limit, cursor) -> CursorPage[Tool]`
- [ ] `SecretRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[Secret]`

### Task 4: Adicionar SQLAlchemyOutboxEventWriter
- [ ] Criar `SQLAlchemyOutboxEventWriter(OutboxEventWriter)` em `tools/infra/repositories.py`
- [ ] Usar `OutboxEventModel` do próprio módulo (verificar se existe ou criar)

### Task 5: Auditar create/update semantics
- [ ] Documentar: `create()` = insert-only com flush + refresh
- [ ] `update()` = load-and-set fields

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado como composição com métodos protegidos
- [ ] `list_by_project` e `list_by_agent` têm equivalentes `paginate_by_*`
- [ ] `SQLAlchemyOutboxEventWriter` criado e funcional
- [ ] Nenhum ORM model vaza fora do infra
- [ ] Testes do tools passam
