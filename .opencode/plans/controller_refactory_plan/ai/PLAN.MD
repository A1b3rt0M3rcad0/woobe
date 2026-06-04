# Controller Refactoring Plan — AI (FASE 4)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar controllers implementando `Controller` interface
4. Criar composers para cada use case
5. Remover `application/providers.py`
6. Extrair lógica de `list_provider_credentials` e `list_agents` para use cases

## Inventory

### Current: `presentation/controllers.py` (6 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `POST /credentials` | `create_provider_credential` | Usa `Depends`, chama provider |
| `GET /credentials` | `list_provider_credentials` | Usa `Depends`, instancia repo direto, sem use case |
| `POST /agents` | `create_agent` | Usa `Depends`, chama provider |
| `GET /agents` | `list_agents` | Usa `Depends`, instancia repo direto, sem use case |
| `GET /agents/{agent_id}` | `get_agent` | Usa `Depends`, chama provider |
| `PATCH /agents/{agent_id}` | `update_agent` | Usa `Depends`, chama provider |

### Current: `application/providers.py`
- `get_create_agent_use_case(session)` → `CreateAgentUseCase`
- `get_create_provider_credential_use_case(session)` → `CreateProviderCredentialUseCase`
- `get_update_agent_use_case(session)` → `UpdateAgentUseCase`
- `get_agent_by_id_use_case(session)` → `_GetAgentByIdUseCase` (private)

### Current: `service/use_cases.py`
- `CreateProviderCredentialUseCase`
- `CreateAgentUseCase`
- `UpdateAgentUseCase`

Use cases faltantes:
- `ListProviderCredentialsUseCase`
- `ListAgentsUseCase`
- `GetAgentByIdUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Promover use cases privados para públicos
- `_GetAgentByIdUseCase` → `GetAgentByIdUseCase`

### Task 3: Criar use cases faltantes
- `ListProviderCredentialsUseCase`
- `ListAgentsUseCase`

### Task 4: Criar controllers
- `create_provider_credential_controller.py`
- `list_provider_credentials_controller.py`
- `create_agent_controller.py`
- `list_agents_controller.py`
- `get_agent_controller.py`
- `update_agent_controller.py`

### Task 5: Criar composers
Um composer por use case.

### Task 6: Criar `presentation/routes.py`
Rotas mínimas de 3 linhas.

### Task 7: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListProviderCredentialsUseCase`, `ListAgentsUseCase`, `GetAgentByIdUseCase` criados
- [ ] `application/providers.py` removido
- [ ] `ruff check` e `pyright` passam
