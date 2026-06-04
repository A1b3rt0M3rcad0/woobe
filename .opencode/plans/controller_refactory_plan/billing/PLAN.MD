# Controller Refactoring Plan — Billing (FASE 3)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Substituir `BillingProviders` class-based por composers individuais
4. Criar controllers implementando `Controller` interface
5. Manter use cases existentes

## Inventory

### Current: `presentation/controllers.py` (4 rotas)
| Rota | Handler | Problemas |
|---|---|---|
| `POST /plans` | `create_plan` | Usa `Depends`, instancia `BillingProviders` na rota |
| `GET /plans` | `list_plans` | Usa `Depends`, instancia `BillingProviders` na rota |
| `POST /subscriptions` | `create_subscription` | Usa `Depends`, instancia `BillingProviders` na rota |
| `GET /organizations/{org_id}/subscription` | `get_organization_subscription` | Usa `Depends`, instancia `BillingProviders` na rota |

### Current: `application/providers.py` (class-based)
- `BillingProviders.create_plan_use_case()` → `CreatePlanUseCase`
- `BillingProviders.list_active_plans()` → direct repo call (sem use case)
- `BillingProviders.get_organization_subscription(org_id)` → `_GetOrganizationSubscriptionUseCase` (private)
- `BillingProviders.create_subscription_use_case()` → `CreateSubscriptionUseCase`

### Current: `service/use_cases.py`
- `CreatePlanUseCase`
- `CreateCustomerUseCase`
- `CreateSubscriptionUseCase`
- `HandlePaymentEventUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/`
- `application/composers/`
- `presentation/routes.py`

### Task 2: Criar use cases faltantes
- `ListActivePlansUseCase` (hoje é `list_active_plans()` direto no provider)
- `GetOrganizationSubscriptionUseCase` (hoje é privado no provider)

### Task 3: Criar controllers em `presentation/controllers/`
- `create_plan_controller.py`
- `list_plans_controller.py`
- `create_subscription_controller.py`
- `get_organization_subscription_controller.py`

### Task 4: Criar composers em `application/composers/`
Um composer por use case.

### Task 5: Criar `presentation/routes.py`
Rotas mínimas de 3 linhas.

### Task 6: Remover `application/providers.py`
Substituir `BillingProviders` class pelos composers.

## Acceptance Criteria

- [ ] `presentation/routes.py` com endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] `ListActivePlansUseCase` e `GetOrganizationSubscriptionUseCase` criados
- [ ] `BillingProviders` removido
- [ ] `ruff check` e `pyright` passam
