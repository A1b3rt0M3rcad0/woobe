# Controller Refactoring Plan — Runtime (FASE 6)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar controllers implementando `Controller` interface
4. Criar composers para cada use case
5. Remover `application/providers.py`
6. Extrair `list_messages` (hoje com repo direto) para use case

## Inventory

### Current: `presentation/controllers.py` (3 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `POST /sessions` | `create_session` | Usa `Depends` |
| `POST /ask` | `ask` | Usa `Depends` |
| `GET /sessions/{session_id}/messages` | `list_messages` | Usa `Depends` — provavelmente chama repo direto |

### Current: `application/providers.py`
- `provide_create_session_uc(session)` → `CreateSessionUseCase`
- `provide_send_message_uc(session)` → `SendMessageUseCase`
- `provide_list_messages(session, ...)` → direct repo

### Current: `service/use_cases.py`
- `CreateSessionUseCase`
- `SendMessageUseCase`

Use cases faltantes:
- `ListMessagesUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Criar use cases faltantes
- `ListMessagesUseCase`

### Task 3: Criar controllers
- `create_session_controller.py`
- `send_message_controller.py` (ou `ask_controller.py`)
- `list_messages_controller.py`

### Task 4: Criar composers
Um composer por use case.

### Task 5: Criar `presentation/routes.py`

### Task 6: Remover `application/providers.py`

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListMessagesUseCase` criado
- [ ] `application/providers.py` removido
- [ ] `ruff check` e `pyright` passam
