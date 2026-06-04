# Controller Refactoring Plan — Observability (FASE 9)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Substituir `ObservabilityProviders` class-based por composers individuais
4. Criar controllers implementando `Controller` interface
5. Promover use cases privados para públicos

## Inventory

### Current: `presentation/controllers.py` (4 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `GET /traces` | `list_traces` | Usa `Depends`, instancia `ObservabilityProviders` na rota |
| `POST /traces` | `create_trace` | Usa `Depends`, instancia `ObservabilityProviders` na rota |
| `POST /traces/{trace_id}/events` | `add_trace_event` | Usa `Depends`, instancia `ObservabilityProviders` na rota |
| `GET /traces/{trace_id}` | `get_trace` | Usa `Depends`, instancia `ObservabilityProviders` na rota |

### Current: `application/providers.py` (class-based)
- `ObservabilityProviders.create_trace_use_case()` → `CreateTraceUseCase`
- `ObservabilityProviders.create_trace_event_use_case()` → `CreateTraceEventUseCase`
- `ObservabilityProviders.get_trace_use_case()` → `_GetTraceUseCase` (private)
- `ObservabilityProviders.list_traces_use_case()` → `_ListTracesUseCase` (private)

### Current: `service/use_cases.py`
- `CreateTraceUseCase`
- `CreateTraceEventUseCase`
- `GetTraceUseCase`

Use cases faltantes:
- `ListTracesUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Criar use cases faltantes
- `ListTracesUseCase`

### Task 3: Promover use cases privados
- `_GetTraceUseCase` → `GetTraceUseCase` (verificar se já existe como público)

### Task 4: Criar controllers
- `create_trace_controller.py`
- `list_traces_controller.py`
- `add_trace_event_controller.py`
- `get_trace_controller.py`

### Task 5: Criar composers
Um composer por use case.

### Task 6: Criar `presentation/routes.py`

### Task 7: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListTracesUseCase` criado
- [ ] `ObservabilityProviders` removido
- [ ] `ruff check` e `pyright` passam
