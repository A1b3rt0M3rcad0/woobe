# Repository Refactoring Plan — Shared (FASE 0)

## Goals

1. Renomear `BaseRepository` para `BaseSQLAlchemyRepository` com métodos protegidos
2. Eliminar ambiguidade entre métodos públicos do base e interfaces de domínio
3. Remover `list_all()` — proibido por padrão arquitetural
4. Adicionar `_paginate_models()` como primitive protegida com `CursorPage`
5. Garantir que o base não conheça mappers, entidades de domínio, ou regras de negócio

## Inventory

| Arquivo | Classe | Papel |
|---|---|---|
| `src/shared/infra/repositories/base_repository.py` | `BaseRepository` | Base técnica genérica |
| `src/shared/domain/objects.py` | `CursorPage` | DTO de paginação cursor-based |

## Diagnosis

### Problema 1: Nome genérico `BaseRepository`
O nome `BaseRepository` é genérico demais. O skill recomenda `BaseSQLAlchemyRepository` para deixar explícito que é uma abstração técnica de SQLAlchemy, não um repositório de domínio.

### Problema 2: Métodos públicos com nomes de domínio
- `get_by_id(id) -> T | None` → conflita com `UserRepository.get_by_id(user_id) -> User | None`
- `delete(model)` → conflita com `UserRepository.delete(user_id)`
- Ambos retornam ORM models, enquanto as interfaces de domínio retornam entidades

### Problema 3: `list_all()` público
Método `list_all()` no base retorna `list[T]` sem filtro, paginação, tenant scope ou ordering. Deve ser removido.

### Problema 4: `self.session` público
Atributo `session` é público — deve ser `_session` (protegido).

### Problema 5: Sem primitive de paginação
Não existe `_paginate_models()` no base. Cada módulo implementa paginação manualmente com `offset/limit` ou sem paginação.

### Problema 6: Sem `_flush` e `_refresh_model`
Cada módulo chama `self.session.flush()` e `self.session.refresh()` diretamente. Deveriam ser métodos protegidos no base.

## Tasks

### Task 1: Renomear classe e arquivo
- [x] Renomear `BaseRepository` → `BaseSQLAlchemyRepository`
- [x] NÃO renomear o arquivo (`base_repository.py`) — a classe exportada é o contrato

### Task 2: Proteger atributos e métodos
- [x] `self.session` → `self._session`
- [x] `async def add(self, model)` → `async def _add_model(self, model) -> T`
- [x] `async def get_by_id(self, id)` → `async def _get_model_by_id(self, id) -> T | None`
- [x] `async def delete(self, model)` → `async def _delete_model(self, model) -> None`
- [x] Adicionar `async def _flush(self) -> None`
- [x] Adicionar `async def _refresh_model(self, model) -> None`

### Task 3: Remover `list_all()`
- [x] Remover o método `list_all()` completamente
- [x] Verificar se há consumers — nenhum módulo chama `list_all()` diretamente

### Task 4: Implementar `_paginate_models()`
- [x] Criar método protegido `_paginate_models(statement, *, limit, cursor)` → `CursorPage[T]`
- [x] Usar `id` como cursor (UUIDv7 é monotônico)
- [x] Fetch `limit + 1` rows para computar `has_next`
- [x] Não expor ORM models — retorna `CursorPage[T]` (model)
- [x] Delegar conversão para `CursorPage[Entity]` ao concreto

### Task 5: Atualizar imports em todos os módulos
- [ ] Atualizar `from shared.infra.repositories.base_repository import BaseRepository` → `BaseSQLAlchemyRepository` (a fazer por módulo)

## Acceptance Criteria

- [ ] `BaseRepository` não existe mais como classe pública
- [ ] `BaseSQLAlchemyRepository` exportado de `shared.infra.repositories.base_repository`
- [ ] Todos os métodos públicos antigos (`add`, `get_by_id`, `delete`, `list_all`) foram removidos
- [ ] Métodos protegidos criados: `_add_model`, `_get_model_by_id`, `_delete_model`, `_flush`, `_refresh_model`
- [ ] `_paginate_models()` implementado e retorna `CursorPage[T]`
- [ ] `self._session` é protegido (atributo com underscore)
- [ ] `list_all()` não existe em nenhum lugar do código
- [ ] Módulo `shared` não importa nada de domínio específico
- [ ] `ruff check` e `pyright` passam
