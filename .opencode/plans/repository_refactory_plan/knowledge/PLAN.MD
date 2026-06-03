# Repository Refactoring Plan — Knowledge

## Goals

1. Migrar de `BaseRepository` (Composition) para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern B (Composition) — não mudar para herança
3. Migrar `list_by_project`, `list_by_collection`, `list_by_agent` para `CursorPage`
4. Auditar `create()`, `update()` semantics
5. Adicionar `SQLAlchemyOutboxEventWriter` (atualmente ausente)

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `DocumentCollectionRepository` | `SQLAlchemyDocumentCollectionRepository` | `DocumentCollectionModel` | `DocumentCollection` | Composition | ❌ |
| `DocumentRepository` | `SQLAlchemyDocumentRepository` | `DocumentModel` | `Document` | Composition | ❌ |
| `AgentCollectionRepository` | `SQLAlchemyAgentCollectionRepository` | `AgentCollectionModel` | `AgentCollection` | Composition | ❌ |
| `DocumentChunkRepository` | `SQLAlchemyDocumentChunkRepository` | `DocumentChunkModel` | `DocumentChunk` | Composition | ❌ |

## Diagnosis

### Pattern: Composition
Todos os 4 usam `self._base = BaseRepository(session, Model)` como composição.

Chamam `self._base.get_by_id()`, `self._base.add()`, `self._base.delete()`.

### List methods sem paginação (4 métodos)

| Repositório | Método | Retorno | Observação |
|---|---|---|---|
| `DocumentCollectionRepository` | `list_by_project(project_id)` | `list[DocumentCollection]` | Sem paginação |
| `DocumentRepository` | `list_by_collection(collection_id)` | `list[Document]` | Sem paginação |
| `AgentCollectionRepository` | `list_by_agent(agent_id)` | `list[AgentCollection]` | Sem paginação |
| `DocumentChunkRepository` | `list_by_document(doc_id, offset, limit)` | `list[DocumentChunk]` | Usa offset/limit — migrar para cursor |

### Create semantics
- `create()` em todos = insert-only (`self.session.add(model)` + `flush()` + `refresh()`)
- Consistente entre os 4 repositórios

### Update semantics
- `update()` em `DocumentCollectionRepository` e `DocumentRepository` = load-and-set fields, retorna entity
- `update()` NÃO existe em `AgentCollectionRepository` e `DocumentChunkRepository` (não necessário)

### Delete semantics
- `delete(id)` = load model + `self._base.delete(model)`
- `SQLAlchemyDocumentCollectionRepository.delete()` e `SQLAlchemyDocumentRepository.delete()` levantam `CollectionNotFoundError`/`DocumentNotFoundError` se não encontrar
- `SQLAlchemyAgentCollectionRepository.delete()` levanta `CollectionNotFoundError` também (import dentro do método — precisa corrigir)

### Outbox
❌ Nenhum dos 4 repositórios tem `SQLAlchemyOutboxEventWriter`. O módulo não publica eventos.

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository na composição
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 4 repositórios
- [ ] `self._base = BaseSQLAlchemyRepository(session, Model)`

### Task 2: Substituir chamadas para métodos protegidos
- [ ] `self._base.get_by_id(id)` → `await self._base._get_model_by_id(id)`
- [ ] `self._base.add(model)` → `await self._base._add_model(model)`
- [ ] `self._base.delete(model)` → `await self._base._delete_model(model)`
- [ ] `self.session.add(model)` → `await self._base._add_model(model)` (nos `create()`)
- [ ] `self.session.flush()` → `await self._base._flush()`
- [ ] `self.session.refresh(model)` → `await self._base._refresh_model(model)`

### Task 3: Migrar list methods para CursorPage (Option B)
- [ ] `DocumentCollectionRepository`: adicionar `paginate_by_project(project_id, *, limit, cursor) -> CursorPage[DocumentCollection]`
- [ ] `DocumentRepository`: adicionar `paginate_by_collection(collection_id, *, limit, cursor) -> CursorPage[Document]`
- [ ] `AgentCollectionRepository`: adicionar `paginate_by_agent(agent_id, *, limit, cursor) -> CursorPage[AgentCollection]`
- [ ] `DocumentChunkRepository`: migrar `list_by_document` de offset/limit para cursor

### Task 4: Adicionar SQLAlchemyOutboxEventWriter
- [ ] Criar `SQLAlchemyOutboxEventWriter(OutboxEventWriter)` em `knowledge/infra/repositories.py`
- [ ] Usar `OutboxEventModel` do próprio módulo (já existe em `knowledge/infra/models.py`)
- [ ] Seguir o mesmo padrão dos outros módulos (sem commit, add na session)

### Task 5: Corrigir import dentro de AgentCollectionRepository.delete()
- [ ] Mover `from modules.knowledge.domain.errors import CollectionNotFoundError` para o topo do arquivo

### Task 6: Auditar create/update semantics
- [ ] Documentar: `create()` = insert-only com flush + refresh
- [ ] `update()` = load-and-set fields (sem `save()`)

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado como composição com métodos protegidos
- [ ] `list_by_*` têm equivalentes `paginate_by_*` retornando `CursorPage[Entity]`
- [ ] `SQLAlchemyOutboxEventWriter` criado e funcional
- [ ] `CollectionNotFoundError` importado corretamente (fora do método)
- [ ] Nenhum ORM model vaza fora do infra
- [ ] Testes do knowledge passam
