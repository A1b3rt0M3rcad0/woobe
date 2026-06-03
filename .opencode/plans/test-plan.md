# Plano de Testes — ProjectRAI

## Stack

- **Framework:** pytest >=8.0
- **Async:** pytest-asyncio
- **Mock:** pytest-mock / unittest.mock
- **HTTP:** httpx (AsyncClient para FastAPI)
- **DB em testes:** SQLite (aiosqlite) ou testcontainers (opcional)
- **Cobertura:** pytest-cov

## Estrutura de arquivos

```
tests/
  conftest.py                    # Fixtures globais (app, engine, session)
  helpers.py                     # Fábricas de entidades, mocks reutilizáveis

  unit/
    conftest.py                  # Mock repositories como fixtures
    test_identity/
      test_entities.py           # User, Organization, Member, Invite, Session
      test_enums.py              # UserStatus, MemberRole, InviteStatus...
      test_errors.py             # EmailAlreadyExistsError, UserNotFoundError...
      test_dtos.py               # CreateUserInput/Output, CreateOrganizationInput/Output...
      test_use_cases.py          # CreateUserUseCase, CreateOrganizationUseCase...
    test_core/
      test_entities.py
      test_enums.py
      test_errors.py
      test_dtos.py
      test_use_cases.py          # CreateProjectUseCase, CreateApiKeyUseCase
    test_ai/
      test_entities.py
      test_enums.py
      test_errors.py
      test_use_cases.py          # CreateAgentUseCase, CreateProviderCredentialUseCase
    test_knowledge/
      test_use_cases.py          # CreateCollectionUseCase, UploadDocumentUseCase, SearchChunksUseCase
    test_runtime/
      test_use_cases.py          # CreateSessionUseCase, SendMessageUseCase
    test_tools/
      test_use_cases.py          # CreateToolUseCase, CreateSecretUseCase
    test_metering/
      test_use_cases.py          # RecordUsageUseCase
    test_billing/
      test_use_cases.py          # CreatePlanUseCase, CreateSubscriptionUseCase
    test_observability/
      test_use_cases.py          # CreateTraceUseCase, GetTraceUseCase
    test_shared/
      test_objects.py            # CursorPage
      test_errors.py             # DomainError, NotFoundError, ConflictError
      test_crypto.py             # hash_password, verify_password, encrypt_secret, decrypt_secret
      test_config.py             # Settings

  integration/
    conftest.py                  # Engine + Session + Base metadata + tables
    test_repositories/
      test_identity_repositories.py   # CRUD + queries
      test_core_repositories.py
      test_knowledge_repositories.py
      test_runtime_repositories.py
      test_tools_repositories.py
    test_mappers/
      test_identity_mappers.py        # Model ↔ Entity
      test_core_mappers.py
    test_api/
      test_identity_api.py            # HTTP endpoints com TestClient + DB real
      test_core_api.py
      test_ai_api.py
      test_knowledge_api.py
      test_runtime_api.py

  e2e/
    test_flow_signup_to_ask.py   # Fluxo completo: signup → org → project → api_key → agent → ask
```

## Dependências (pyproject.toml)

```toml
[project.optional-dependencies]
test = [
    "pytest>=8.0",
    "pytest-asyncio>=0.25",
    "pytest-mock>=3.14",
    "httpx>=0.28",
    "aiosqlite>=0.21",
    "pytest-cov>=6.0",
]
```

## Fixtures globais (tests/conftest.py)

```python
@pytest.fixture
def anyio_backend():
    return "asyncio"

@pytest.fixture
def app():
    from main import create_app
    return create_app()

@pytest.fixture
async def async_client(app):
    from httpx import AsyncClient, ASGITransport
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
```

## Fixtures de mock (tests/unit/conftest.py)

Para cada módulo, criar mock repositories:

```python
@pytest.fixture
def mock_user_repo(mocker):
    repo = mocker.AsyncMock(spec=UserRepository)
    return repo

@pytest.fixture
def mock_outbox(mocker):
    repo = mocker.AsyncMock(spec=OutboxEventWriter)
    return repo
```

## Testes por camada

### 1. Unit — Domain Entities

Testar criação de entidades com valores válidos e inválidos:

```python
class TestUserEntity:
    def test_create_user_defaults(self):
        user = User(email="test@example.com", password=b"hash")
        assert user.status == UserStatus.active
        assert user.id is not None

    def test_user_equality(self):
        user = User(email="a@b.com", password=b"pwd")
        assert isinstance(user.id, UUID)
```

### 2. Unit — Use Cases (com mocks)

Testar sucesso e cada cenário de erro:

```python
class TestCreateUserUseCase:
    @pytest.mark.asyncio
    async def test_create_user_success(self, mock_user_repo, mock_outbox):
        mock_user_repo.get_by_email.return_value = None
        mock_user_repo.save.return_value = User(
            id=uuid6.uuid7(), email="test@example.com",
            password=b"hash", created_at=datetime.now(UTC),
        )
        uc = CreateUserUseCase(user_repo=mock_user_repo, outbox=mock_outbox)
        result = await uc.execute(CreateUserInput(email="test@example.com", password="secret"))
        assert result.email == "test@example.com"
        mock_user_repo.save.assert_awaited_once()
        mock_outbox.write.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_user_duplicate_email(self, mock_user_repo, mock_outbox):
        mock_user_repo.get_by_email.return_value = User(email="dup@test.com", password=b"h")
        uc = CreateUserUseCase(user_repo=mock_user_repo, outbox=mock_outbox)
        with pytest.raises(EmailAlreadyExistsError):
            await uc.execute(CreateUserInput(email="dup@test.com", password="secret"))
        mock_user_repo.save.assert_not_called()
```

### 3. Integration — Repositories

Usar SQLite (aiosqlite) + SQLAlchemy para testar persistência real:

```python
@pytest.fixture
async def db_session():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with SessionManager(engine) as manager:
        yield manager.session
    await engine.dispose()

class TestSQLAlchemyUserRepository:
    @pytest.mark.asyncio
    async def test_save_and_get_by_email(self, db_session):
        repo = SQLAlchemyUserRepository(db_session)
        user = User(email="test@example.com", password=b"hash123")
        saved = await repo.save(user)
        assert saved.id is not None

        found = await repo.get_by_email("test@example.com")
        assert found is not None
        assert found.email == "test@example.com"
```

### 4. Integration — API (HTTP)

Testar endpoints FastAPI com TestClient + DB:

```python
class TestIdentityAPI:
    @pytest.mark.asyncio
    async def test_create_user(self, async_client):
        resp = await async_client.post("/identity/users", json={
            "email": "new@user.com",
            "password": "strong123",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["success"] is True
        assert "id" in data["data"]
```

### 5. E2E — Fluxo completo

```python
@pytest.mark.asyncio
async def test_full_flow(async_client):
    # 1. Create user
    r = await async_client.post("/identity/users", json={"email": "a@b.com", "password": "x"})
    user_id = r.json()["data"]["id"]

    # 2. Create organization
    r = await async_client.post("/identity/organizations", json={"name": "MyOrg", "slug": "myorg"})
    org_id = r.json()["data"]["id"]

    # 3. Add member
    r = await async_client.post(f"/identity/organizations/{org_id}/members", json={
        "user_id": user_id, "role": "owner",
    })
    assert r.status_code == 201

    # 4. Create project
    r = await async_client.post("/core/projects", json={
        "organization_id": org_id, "name": "Proj", "slug": "proj",
    })
    project_id = r.json()["data"]["id"]

    # 5. Create API key
    r = await async_client.post(f"/core/projects/{project_id}/api-keys", json={"name": "dev"})
    assert r.status_code == 201
```

---

## Ordem de execução sugerida

1. Configurar pytest + dependências (pyproject.toml)
2. Criar `tests/conftest.py` (app, async_client, anyio_backend)
3. Criar `tests/helpers.py` (entity factories)
4. Unit tests: módulo a módulo (identity → core → ai → knowledge → runtime → tools → metering → billing → observability)
5. Integration tests: repositories + mappers
6. API integration tests
7. E2E flow test
8. Rodar `pytest tests/ -v` e corrigir falhas
