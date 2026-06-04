# Controller Refactoring Plan — Identity (FASE 1)

## Goals

1. Separar `controllers.py` em rotas mínimas + controllers + composers
2. Eliminar `Depends(get_session_manager)` de todas as rotas
3. Criar um controller class por use case (`Controller` interface)
4. Criar um composer por use case (`TransactionalHandler`)
5. Remover `application/providers.py` — substituir pelos composers
6. Garantir que controllers não importam FastAPI

## Inventory

### Current: `presentation/controllers.py` (13 rotas, 284 linhas)
| Rota | Handler | Problemas |
|---|---|---|
| `GET /organizations` | `list_organizations` | Usa `Depends`, cria SQLAlchemy statement direto na rota, sem use case |
| `GET /users/me` | `get_current_user` | Hardcoded, sem use case |
| `POST /auth/login` | `login` | Usa `Depends`, instancia repo direto, retorna `JSONResponse` manual |
| `POST /auth/register` | `register` | Usa `Depends`, chama 3 use cases na mesma rota, sem transação atômica |
| `POST /users` | `create_user` | Usa `Depends`, chama provider |
| `POST /organizations` | `create_organization` | Usa `Depends`, chama provider |
| `POST /organizations/{org_id}/members` | `add_member` | Usa `Depends`, chama provider |
| `GET /organizations/{org_id}` | `get_organization` | Usa `Depends`, instancia repo direto |
| `PATCH /organizations/{org_id}` | `update_organization` | Usa `Depends`, chama provider |
| `GET /organizations/{org_id}/members` | `list_members` | Usa `Depends`, instancia repo direto |
| `POST /organizations/{org_id}/invites` | `create_invite` | Usa `Depends`, instancia `InviteUserUseCase` + repos na rota |
| `GET /organizations/{org_id}/invites` | `list_invites` | Usa `Depends`, instancia repo direto |
| `GET /users/{user_id}` | `get_user` | Usa `Depends`, chama provider |

### Current: `application/providers.py`
Providers function-based:
- `get_create_user_use_case(session)` → `CreateUserUseCase`
- `get_create_organization_use_case(session)` → `CreateOrganizationUseCase`
- `get_add_member_use_case(session)` → `AddMemberToOrganizationUseCase`
- `get_invite_user_use_case(session)` → `InviteUserUseCase`
- `get_user_by_id_use_case(session)` → `_GetUserByIdUseCase` (private)
- `get_update_organization_use_case(session)` → `UpdateOrganizationUseCase`
- `get_organization_repo(session)` → raw repository
- `get_member_repo(session)` → raw repository
- `get_invite_repo(session)` → raw repository

### Current: `service/use_cases.py`
- `CreateUserUseCase`
- `CreateOrganizationUseCase`
- `AddMemberToOrganizationUseCase`
- `UpdateOrganizationUseCase`
- `InviteUserUseCase`

Use cases que não existem (lógica direto na rota):
- `ListOrganizationsUseCase`
- `GetCurrentUserUseCase`
- `LoginUseCase`
- `RegisterUseCase`
- `GetOrganizationUseCase`
- `ListMembersUseCase`
- `ListInvitesUseCase`
- `GetUserUseCase`

## Tasks

### Task 1: Criar estrutura de diretórios
- `presentation/controllers/` — um arquivo por controller
- `application/composers/` — um arquivo por composer
- `presentation/routes.py` — rotas mínimas

### Task 2: Mover rotas para `presentation/routes.py`
Cada rota vira 3 linhas:
```python
@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    handler = list_organizations_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
```

### Task 3: Criar controllers em `presentation/controllers/`
Para cada endpoint, criar uma classe `Controller`:
- `list_organizations_controller.py` → `ListOrganizationsController`
- `login_controller.py` → `LoginController`
- `register_controller.py` → `RegisterController`
- `create_user_controller.py` → `CreateUserController`
- `create_organization_controller.py` → `CreateOrganizationController`
- `add_member_controller.py` → `AddMemberController`
- `get_organization_controller.py` → `GetOrganizationController`
- `update_organization_controller.py` → `UpdateOrganizationController`
- `list_members_controller.py` → `ListMembersController`
- `create_invite_controller.py` → `CreateInviteController`
- `list_invites_controller.py` → `ListInvitesController`
- `get_user_controller.py` → `GetUserController`
- `get_current_user_controller.py` → `GetCurrentUserController`

### Task 4: Criar use cases faltantes
Criar use cases para lógica que hoje está direto na rota:
- `ListOrganizationsUseCase`
- `LoginUseCase`
- `RegisterUseCase`
- `GetOrganizationUseCase`
- `ListMembersUseCase`
- `ListInvitesUseCase`
- `GetUserUseCase`
- `GetCurrentUserUseCase`

> RegisterUseCase envolve 3 operações (create user + create org + add member) — precisa ser atômico dentro de um único UoW.

### Task 5: Criar composers em `application/composers/`
Para cada use case, criar `nome_composer.py`:
```python
def list_organizations_composer() -> TransactionalHandler:
    uow = PostgresUnitOfWork(engine)
    repo = SQLAlchemyOrganizationRepository(uow)
    use_case = ListOrganizationsUseCase(repo)
    controller = ListOrganizationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
```

### Task 6: Remover `application/providers.py`
Toda lógica de providers migra para os composers.

### Task 7: Adaptar `main.py` se necessário
Verificar import do router (de `controllers` para `routes`).

### Task 8: Atualizar `presentation/schemas.py`
Manter como schemas de request/response Pydantic — controllers usam para validar dados.

### Task 9: Migrar `list_organizations` (rota com SQL puro)
Extrair lógica de `select(OrganizationModel).order_by(...)` para `ListOrganizationsUseCase`.

### Task 10: Migrar `register` (rota com 3 use cases)
Criar `RegisterUseCase` que executa create_user + create_org + add_member em uma transação.

## Acceptance Criteria

- [ ] `presentation/routes.py` contém apenas endpoints de 3 linhas
- [ ] Nenhuma rota importa `Depends(get_session_manager)`
- [ ] Nenhuma rota instancia repositório ou use case
- [ ] Todo controller implementa `Controller` interface
- [ ] Todo composer retorna `TransactionalHandler`
- [ ] `application/providers.py` removido
- [ ] `LoginUseCase`, `RegisterUseCase`, etc criados para lógica hoje nas rotas
- [ ] `RegisterUseCase` executa 3 operações em uma transação
- [ ] `ruff check` e `pyright` passam
- [ ] Testes de unidade do identity passam
