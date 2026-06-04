# Controller Refactoring Plan — Knowledge (FASE 5)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar controllers implementando `Controller` interface
4. Criar composers para cada use case
5. Remover `application/providers.py`
6. Extrair `get_collection` e `get_document` (hoje com repo direto) para use cases

## Inventory

### Current: `presentation/controllers.py` (10 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `GET /collections` | `list_collections` | Usa `Depends` — verificar implementação exata |
| `POST /collections` | `create_collection` | Usa `Depends` |
| `GET /agent-collections` | `list_agent_collections` | Usa `Depends` |
| `POST /agent-collections` | `attach_collection` | Usa `Depends` |
| `DELETE /agent-collections/{link_id}` | `detach_collection` | Usa `Depends` |
| `GET /collections/{collection_id}` | `get_collection` | Usa `Depends` — instancia repo direto |
| `GET /documents` | `list_documents` | Usa `Depends` |
| `POST /documents` | `upload_document` | Usa `Depends` |
| `GET /documents/{document_id}` | `get_document` | Usa `Depends` — instancia repo direto |
| `POST /search` | `search_chunks` | Usa `Depends` |

### Current: `application/providers.py`
- `provide_create_collection_uc(session)` → `CreateCollectionUseCase`
- `provide_upload_document_uc(session)` → `UploadDocumentUseCase`
- `provide_search_chunks_uc(session)` → `SearchChunksUseCase`
- `provide_list_agent_collections_uc(session)` → `ListAgentCollectionsUseCase`
- `provide_attach_collection_uc(session)` → `AttachCollectionUseCase`
- `provide_detach_collection_uc(session)` → `DetachCollectionUseCase`
- `provide_get_collection(session, id)` → direct repo
- `provide_get_document(session, id)` → direct repo

### Current: `service/use_cases.py`
- `ListAgentCollectionsUseCase`
- `AttachCollectionUseCase`
- `DetachCollectionUseCase`
- `CreateCollectionUseCase`
- `UploadDocumentUseCase`
- `SearchChunksUseCase`

Use cases faltantes:
- `ListCollectionsUseCase`
- `GetCollectionUseCase`
- `ListDocumentsUseCase`
- `GetDocumentUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Criar use cases faltantes
- `ListCollectionsUseCase`
- `GetCollectionUseCase`
- `ListDocumentsUseCase`
- `GetDocumentUseCase`

### Task 3: Criar controllers
Um controller por endpoint (10 controllers).

### Task 4: Criar composers
Um composer por use case.

### Task 5: Criar `presentation/routes.py`
Rotas mínimas de 3 linhas.

### Task 6: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListCollectionsUseCase`, `GetCollectionUseCase`, `ListDocumentsUseCase`, `GetDocumentUseCase` criados
- [ ] `application/providers.py` removido
- [ ] `ruff check` e `pyright` passam
