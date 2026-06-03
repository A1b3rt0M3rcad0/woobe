# Repository Refactoring Plan — Billing

## Goals

1. Migrar de `BaseRepository` para `BaseSQLAlchemyRepository` (protegido)
2. Manter Pattern A (Dual Inheritance)
3. Nenhum list method existente — sem necessidade de paginação inicial
4. Auditar `save()` semantics (insert-only com refresh)
5. Outbox já existe — preservar

## Inventory

| Domain Interface | Concrete Impl | Model | Entity | Padrão | Outbox |
|---|---|---|---|---|---|
| `PlanRepository` | `SQLAlchemyPlanRepository` | `PlanModel` | `Plan` | Dual | — |
| `CustomerRepository` | `SQLAlchemyCustomerRepository` | `CustomerModel` | `Customer` | Dual | — |
| `SubscriptionRepository` | `SQLAlchemySubscriptionRepository` | `SubscriptionModel` | `Subscription` | Dual | — |
| `PaymentEventRepository` | `SQLAlchemyPaymentEventRepository` | `PaymentEventModel` | `PaymentEvent` | Dual | — |
| — | `SQLAlchemyOutboxEventWriter` | `OutboxEventModel` | — | — | ✅ |

## Diagnosis

### Pattern: Dual Inheritance
Todos os 4 repositórios usam `BaseRepository[Model], Interface`.

### Métodos
- `PlanRepository`: só `save()` — sem `get_by_id`, `get_by_code`, `list_active`, `delete` declarados na interface mas não implementados? **Verificar**.
- `CustomerRepository`: só `save()` — mesmos métodos ausentes.
- `SubscriptionRepository`: só `save()` — mesmos métodos ausentes.
- `PaymentEventRepository`: `save()`, `get_by_id` (chama `self.session.get()` diretamente, não `super()`), `get_by_provider_event`.

⚠️ **Risco**: Repositórios `PlanRepository`, `CustomerRepository`, `SubscriptionRepository` implementam a interface mas não implementam todos os métodos abstratos. Podem estar quebrados ou incompletos.

### Save semantics
- Todos chamam `flush()` + `refresh()` após `add()` — consistente.

### Paginação
- Nenhum list method existe. Billing não requer paginação inicial.

## Tasks

### Task 1: Atualizar BaseSQLAlchemyRepository
- [ ] Trocar `BaseRepository` → `BaseSQLAlchemyRepository` nos 4 repositórios

### Task 2: Substituir chamadas para métodos protegidos
- [ ] `self.session.add(model)` → `await self._add_model(model)`
- [ ] `self.session.flush()` → `await self._flush()`
- [ ] `self.session.refresh(model)` → `await self._refresh_model(model)`
- [ ] `self.session.get(PaymentEventModel, event_id)` → `await self._get_model_by_id(event_id)`

### Task 3: Auditar implementações incompletas
- [ ] Verificar se `PlanRepository` implementa todos os métodos de `PlanRepository` ABC
- [ ] Verificar se `CustomerRepository` implementa todos os métodos de `CustomerRepository` ABC
- [️] Verificar se `SubscriptionRepository` implementa todos os métodos de `SubscriptionRepository` ABC
- [ ] Implementar métodos faltantes se necessário

### Task 4: Manter save semantics
- [ ] `save()` = insert-only com `flush()` + `refresh()` — manter

## Acceptance Criteria

- [ ] `BaseSQLAlchemyRepository` usado com métodos protegidos
- [ ] Todos os métodos abstratos das interfaces estão implementados
- [ ] `flush()` + `refresh()` mantido e padronizado
- [ ] Outbox preservado
- [ ] Testes do billing passam
