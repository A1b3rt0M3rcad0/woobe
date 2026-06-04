# Controller Refactoring Plan — Metering (FASE 8)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Substituir `MeteringProviders` class-based por composers individuais
4. Criar controllers implementando `Controller` interface
5. Promover use cases privados para públicos

## Inventory

### Current: `presentation/controllers.py` (3 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `POST /usage-events` | `record_usage` | Usa `Depends`, instancia `MeteringProviders` na rota |
| `GET /projects/{project_id}/daily` | `get_project_daily_usage` | Usa `Depends`, instancia `MeteringProviders` na rota |
| `GET /agents/{agent_id}/daily` | `get_agent_daily_usage` | Usa `Depends`, instancia `MeteringProviders` na rota |

### Current: `application/providers.py` (class-based)
- `MeteringProviders.record_usage_use_case()` → `RecordUsageUseCase`
- `MeteringProviders.get_project_daily_usage_use_case()` → `_GetProjectDailyUsageUseCase` (private)
- `MeteringProviders.get_agent_daily_usage_use_case()` → `_GetAgentDailyUsageUseCase` (private)

### Current: `service/use_cases.py`
- `RecordUsageUseCase`
- `GetProjectDailyUsageUseCase`
- `GetAgentDailyUsageUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Promover use cases privados para públicos
- `_GetProjectDailyUsageUseCase` já existe como `GetProjectDailyUsageUseCase` — verificar duplicidade no use_cases.py
- `_GetAgentDailyUsageUseCase` já existe como `GetAgentDailyUsageUseCase` — verificar duplicidade

### Task 3: Criar controllers
- `record_usage_controller.py`
- `get_project_daily_usage_controller.py`
- `get_agent_daily_usage_controller.py`

### Task 4: Criar composers
Um composer por use case.

### Task 5: Criar `presentation/routes.py`

### Task 6: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `MeteringProviders` removido
- [ ] `ruff check` e `pyright` passam
