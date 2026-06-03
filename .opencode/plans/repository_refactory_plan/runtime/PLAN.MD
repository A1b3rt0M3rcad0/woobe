# Repository Refactoring Plan — Runtime

## Goals

1. Migrar de `BaseRepository` (Composition) para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern B (Composition) — não mudar para herança
3. Migrar `list_by_project`, `list_by_session` para `CursorPage`
4. Auditar `create()`, `update()` semantics
5. Adicionar `SQLAlchemyOutboxEventWriter` (atualmente ausente)

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `SessionRepository` | `SQLAlchemySessionRepository` | `SessionModel` | `Session` | Composition | ❌ |
| `MessageRepository` | `SQLAlchemyMessageRepository` | `MessageModel` | `Message` | Composition | ❌ |

## Diagnosis

### Pattern: Composition
Ambos usam `self._base = BaseRepository(session, Model)`.

Chamam `self._base.get_by_id()`, `self._base.delete()`, `self._base.add()`.

### List methods sem paginação (2 métodos)

| Repositório | Método | Retorno | Observação |
|---|---|---|---|
| `SessionRepository` | `list_by_project(project_id)` | `list[Session]` | Sem paginação |
| `MessageRepository` | `list_by_session(session_id, offset, limit)` | `list[Message]` | Usa offset/limit — migrar para cursor |

### Create semantics
- `create()` em ambos = insert-only (`self.session.add(model)` + `flush()` + `refresh()`)
- Consistente

### Update semantics
- `SessionRepository.update(session)` = load-and-set fields, retorna entity
- `MessageRepository` não tem `update()` (mensagens são imutáveis)

### Delete semantics
- `SessionRepository.delete(session_id)` = load + delete, levanta `SessionNotFoundError`
- `MessageRepository.delete_by_session(session_id)` = carrega todas + deleta uma por uma
- Ambos chamam `self._base.delete(model)`

### Outbox
❌ Nenhum dos 2 repositórios tem `SQLAlchemyOutboxEventWriter`. O módulo não publica eventos.

### Outros métodos
- `MessageRepository.count_by_session(session_id)` — não precisa de paginação (retorna int)
- `SessionRepository.get_by_external_id(...)` — query específica

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
- [ ] `SessionRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[Session]`
- [ ] `MessageRepository`: migrar `list_by_session` de offset/limit para cursor e adicionar `paginate_by_session`

### Task 4: Adicionar SQLAlchemyOutboxEventWriter
- [ ] Criar `SQLAlchemyOutboxEventWriter(OutboxEventWriter)` em `runtime/infra/repositories.py`
- [ ] Usar `OutboxEventModel` do próprio módulo (já existe em `runtime/infra/models.py`)

### Task 5: Auditar create/update semantics
- [ ] Documentar: `create()` = insert-only com flush + refresh
- [ ] `update()` = load-and-set fields (apenas em SessionRepository)

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado como composição com métodos protegidos
- [ ] `list_by_project` e `list_by_session` têm equivalentes `paginate_by_*`
- [ ] `SQLAlchemyOutboxEventWriter` criado e funcional
- [ ] Nenhum ORM model vaza fora do infra
- [ ] Testes do runtime passam
