# Controller Refactoring Plan — Core (FASE 2)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar um controller class por use case
4. Criar um composer por use case
5. Remover `application/providers.py` — substituir pelos composers
6. Extrair `update_project` lógica para um use case (hoje está na rota com SQL puro)

## Inventory

### Current: `presentation/controllers.py` (6 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `GET /projects` | `list_projects` | Usa `Depends`, chama provider |
| `POST /projects` | `create_project` | Usa `Depends`, chama provider |
| `GET /projects/{project_id}` | `get_project` | Usa `Depends`, chama provider |
| `PATCH /projects/{project_id}` | `update_project` | Usa `Depends`, instancia repo direto, lógica SQL na rota, sem use case |
| `POST /projects/{project_id}/api-keys` | `create_api_key` | Usa `Depends` + `get_current_user_id`, chama provider |
| `GET /projects/{project_id}/api-keys` | `list_api_keys` | Usa `Depends`, chama provider |

### Current: `application/providers.py`
- `get_create_project_use_case(session)` → `CreateProjectUseCase`
- `get_create_api_key_use_case(session)` → `CreateApiKeyUseCase`
- `list_projects_use_case(session)` → `_ListProjectsUseCase` (private)
- `get_project_by_id_use_case(session)` → `_GetProjectByIdUseCase` (private)
- `list_api_keys_by_project_use_case(session)` → `_ListApiKeysByProjectUseCase` (private)

### Current: `application/dependencies.py`
- `get_current_user_id()` → retorna hardcoded UUID (precisa ser substituído por auth real)

### Current: `service/use_cases.py`
- `CreateProjectUseCase`
- `CreateApiKeyUseCase`

Use cases faltantes (lógica direto na rota ou providers privados):
- `ListProjectsUseCase`
- `GetProjectByIdUseCase`
- `UpdateProjectUseCase`
- `ListApiKeysByProjectUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Promover use cases privados para públicos
- `_ListProjectsUseCase` → `ListProjectsUseCase` (mover para `service/use_cases.py`)
- `_GetProjectByIdUseCase` → `GetProjectByIdUseCase`
- `_ListApiKeysByProjectUseCase` → `ListApiKeysByProjectUseCase`

### Task 3: Criar `UpdateProjectUseCase`
Extrair lógica de `update_project` (hoje na rota com `SQLAlchemyProjectRepository`) para um use case.

### Task 4: Criar controllers em `presentation/controllers/`
- `list_projects_controller.py`
- `create_project_controller.py`
- `get_project_controller.py`
- `update_project_controller.py`
- `create_api_key_controller.py`
- `list_api_keys_controller.py`

### Task 5: Criar composers em `application/composers/`
Um composer por use case, retornando `TransactionalHandler`.

### Task 6: Criar `presentation/routes.py`
Rotas mínimas de 3 linhas, sem `Depends(get_session_manager)`.

### Task 7: Remover `application/providers.py`

### Task 8: Adaptar `get_current_user_id`
Manter como `Depends` por enquanto (auth será refatorada separadamente). O controller recebe `user_id` via `Request.user`.

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `UpdateProjectUseCase` criado com lógica extraída da rota
- [ ] Use cases privados promovidos para públicos
- [ ] `application/providers.py` removido
- [ ] `ruff check` e `pyright` passam
