# Repository Refactoring Plan — Identity

## Goals

1. Migrar de `BaseRepository` (público) para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern A (Dual Inheritance) — `BaseSQLAlchemyRepository[Model] + UserRepository`
3. Migrar `list_by_organization` e `list_by_user` para `CursorPage`
4. Auditar `save()` semantics (insert-only — OK, mas documentar)
5. Padronizar `flush()` vs `flush() + refresh()` entre os 5 repositórios
6. Outbox já existe (`SQLAlchemyOutboxEventWriter`) — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `UserRepository` | `SQLAlchemyUserRepository` | `UserModel` | `User` | Dual | — |
| `OrganizationRepository` | `SQLAlchemyOrganizationRepository` | `OrganizationModel` | `Organization` | Dual | — |
| `OrganizationMemberRepository` | `SQLAlchemyOrganizationMemberRepository` | `OrganizationMemberModel` | `OrganizationMember` | Dual | — |
| `OrganizationInviteRepository` | `SQLAlchemyOrganizationInviteRepository` | `OrganizationInviteModel` | `OrganizationInvite` | Dual | — |
| `UserSessionRepository` | `SQLAlchemyUserSessionRepository` | `UserSessionModel` | `UserSession` | Dual | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Dual Inheritance
Todos os 5 repositórios usam `BaseRepository[Model], Interface`.

Chamam `super().get_by_id(id)` que retorna ORM model → depois convertem com mapper. Isso cria ambiguidade de tipos.

### List methods sem paginação (4 métodos)

| Repositório | Método | Retorno | Consumers |
|---|---|---|---|
| `OrganizationMemberRepository` | `list_by_organization(org_id)` | `list[OrganizationMember]` | `ListMembersUseCase` (futuro) |
| `OrganizationMemberRepository` | `list_by_user(user_id)` | `list[OrganizationMember]` | `ListUserMembershipsUseCase` (futuro) |
| `OrganizationInviteRepository` | `list_by_organization(org_id)` | `list[OrganizationInvite]` | `ListInvitesUseCase` (futuro) |
| `UserSessionRepository` | `list_by_user(user_id)` | `list[UserSession]` | `ListSessionsUseCase` (futuro) |

### Save semantics
- `save()` em todos = insert-only (`self.session.add(model)` + `flush()`)
- `save()` em `OrganizationInviteRepository` e `UserSessionRepository` chamam `flush()` + `refresh()`
- `save()` em `UserRepository`, `OrganizationRepository`, `OrganizationMemberRepository` chamam só `flush()`

### Flush/Refresh inconsistente
- User: `flush()` apenas
- Organization: `flush()` apenas
- OrganizationMember: `flush()` apenas
- OrganizationInvite: `flush()` + `refresh()`
- UserSession: `flush()` + `refresh()`

### Outbox
✅ `SQLAlchemyOutboxEventWriter` implementado corretamente (sem commit, add na session)

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository
- [x] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 5 repositórios

### Task 2: Substituir chamadas para métodos protegidos
- [x] `super().get_by_id(id)` → `await self._get_model_by_id(id)`
- [x] `self.session.add(model)` → `await self._add_model(model)` (onde aplicável)
- [x] `self.session.delete(model)` → `await self._delete_model(model)`
- [x] `self.session.flush()` → `await self._flush()`
- [x] `self.session.refresh(model)` → `await self._refresh_model(model)`

### Task 3: Padronizar flush/refresh
- [x] Decidir: usar `flush()` + `refresh()` em todos os `save()` (para consistência)
- [x] Padronizado: todos os 5 `save()` usam `_add_model` + `_flush` + `_refresh_model`

### Task 4: Migrar list methods para CursorPage (Option B)
- [x] `OrganizationMemberRepository`: adicionar `paginate_by_organization(org_id, *, limit, cursor) -> CursorPage[OrganizationMember]`
- [x] `OrganizationMemberRepository`: adicionar `paginate_by_user(user_id, *, limit, cursor) -> CursorPage[OrganizationMember]`
- [x] `OrganizationInviteRepository`: adicionar `paginate_by_organization(org_id, *, limit, cursor) -> CursorPage[OrganizationInvite]`
- [x] `UserSessionRepository`: adicionar `paginate_by_user(user_id, *, limit, cursor) -> CursorPage[UserSession]`

### Task 5: Atualizar Domain Interfaces
- [x] Adicionar métodos `paginate_by_*` nas interfaces ABC correspondentes
- [x] NÃO remover `list_by_*` antigos ainda (Option B — two-phase migration)
- [x] Marcar `list_by_*` com `# TODO: Remove after pagination migration`

### Task 6: Auditoria de `save()` semantics
- [x] Documentar: `save()` = insert-only (não faz merge/upsert)
- [x] Decisão: manter como insert-only — padronizado com flush+refresh em todos

### Task 7: Preservar OutboxEventWriter
- [x] Nenhuma mudança — `SQLAlchemyOutboxEventWriter` já segue o padrão correto

## Acceptance Criteria

- [ ] Nenhum `BaseRepository` importado em `identity`
- [ ] `BaseSQLAlchemyRepository` usado com métodos protegidos
- [ ] `list_by_organization` e `list_by_user` têm equivalentes `paginate_by_*` retornando `CursorPage[Entity]`
- [ ] `save()` semantics documentadas (insert-only)
- [ ] `flush()`/`refresh()` padronizado ou documentado
- [ ] Domain interfaces não importam SQLAlchemy
- [ ] ORM models não vazam fora do infra
- [ ] Outbox preservado
- [ ] Testes de unidade do identity passam
