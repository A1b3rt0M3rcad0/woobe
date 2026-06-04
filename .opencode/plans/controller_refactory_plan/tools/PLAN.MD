# Controller Refactoring Plan — Tools (FASE 7)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar controllers implementando `Controller` interface
4. Criar composers para cada use case
5. Remover `application/providers.py`
6. Extrair `list_tools_by_agent` (hoje com repo direto) para use case

## Inventory

### Current: `presentation/controllers.py` (5 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `GET /tools` | `list_tools` | Usa `Depends` |
| `POST /tools` | `create_tool` | Usa `Depends` |
| `GET /agents/{agent_id}/tools` | `list_tools_by_agent` | Usa `Depends` — provavelmente chama repo direto |
| `GET /secrets` | `list_secrets` | Usa `Depends` |
| `POST /secrets` | `create_secret` | Usa `Depends` |

### Current: `application/providers.py`
- `provide_create_tool_uc(session)` → `CreateToolUseCase`
- `provide_list_tools_by_agent(session, agent_id)` → direct repo
- `provide_create_secret_uc(session)` → `CreateSecretUseCase`

### Current: `service/use_cases.py`
- `CreateToolUseCase`
- `CreateSecretUseCase`
- `ExecuteToolUseCase`

Use cases faltantes:
- `ListToolsUseCase`
- `ListToolsByAgentUseCase`
- `ListSecretsUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Criar use cases faltantes
- `ListToolsUseCase`
- `ListToolsByAgentUseCase`
- `ListSecretsUseCase`

### Task 3: Criar controllers
Um controller por endpoint (5 controllers).

### Task 4: Criar composers
Um composer por use case.

### Task 5: Criar `presentation/routes.py`

### Task 6: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListToolsUseCase`, `ListToolsByAgentUseCase`, `ListSecretsUseCase` criados
- [ ] `application/providers.py` removido
- [ ] `ruff check` e `pyright` passam
