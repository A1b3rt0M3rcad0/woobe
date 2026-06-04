# Controller Refactoring Plan — Shared (FASE 0)

## Goals

1. Criar camada base de `Request`/`Response` desacoplada do FastAPI
2. Criar interface `Controller` para padronizar todos os controllers
3. Criar `TransactionalHandler` para gerenciar transações automaticamente
4. Criar `UnitOfWork` como abstração de sessão + transação
5. Criar adaptadores `request_adapter`/`response_adapter` para ponte FastAPI ↔ shared
6. Remover `ok()`/`created()`/`error()` que retornam `JSONResponse` — substituir por `response_adapter`

## Inventory

| Arquivo a criar | Classe/Conteúdo | Papel |
|---|---|---|
| `shared/presentation/interface/controller.py` | `Controller(ABC)` | Interface padrão para todos os controllers |
| `shared/presentation/http/request.py` | `Request(BaseModel)` | Request desacoplado do FastAPI |
| `shared/presentation/http/response.py` | `Response(BaseModel)` | Response desacoplado do FastAPI |
| `shared/presentation/http/types.py` | `HttpHandler` | Type alias `Callable[[Request], Coroutine[..., Response]]` |
| `shared/presentation/http/adapter.py` | `request_adapter`, `response_adapter` | Ponte FastAPI → shared |
| `shared/application/transactional_handler.py` | `TransactionalHandler` | Wrapper que abre UoW, executa handler, commita/rollback |
| `shared/infra/config/interface/unit_of_work.py` | `UnitOfWork(ABC)` | Interface abstrata de UoW |
| `shared/infra/database/postgres_unit_of_work.py` | `PostgresUnitOfWork` | Implementação PostgreSQL com `async with uow:` |

| Arquivo existente | Mudança |
|---|---|
| `shared/presentation/responses.py` | Remover ou adaptar — `response_adapter` passa a ser o padrão |
| `shared/presentation/dependencies.py` | Manter temporariamente para compatibilidade, remover após migração |
| `shared/presentation/errors.py` | Adaptar exception handlers para conviver com `TransactionalHandler` |

## Diagnosis

### Problema 1: Response acoplado ao FastAPI
`responses.py` retorna `JSONResponse` diretamente. Isso impede testar controllers sem FastAPI.

### Problema 2: Sem interface de Controller
Controllers são funções soltas. Não há contrato padronizado. Não há como garantir que todo controller implementa `handle(request) -> Response`.

### Problema 3: Transação manual e espalhada
Cada rota depende de `get_session_manager` e gerencia sessão manualmente. `commit`/`rollback` não são centralizados.

### Problema 4: Sem UnitOfWork
`SessionManager` expõe `session` mas não encapsula transação como contexto. Repositórios recebem `session` diretamente em vez de `UnitOfWork`.

### Problema 5: Sem adaptadores
A rota precisa lidar com `FastAPI Request` → extrair body → chamar use case → converter resposta. Não há separação clara entre camada HTTP e camada de aplicação.

## Tasks

### Task 1: Criar `shared/presentation/interface/controller.py`
```python
from abc import ABC, abstractmethod
from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response

class Controller(ABC):
    @abstractmethod
    async def handle(self, request: Request) -> Response: ...
```

### Task 2: Criar `shared/presentation/http/request.py`
```python
from typing import Any
from pydantic import BaseModel, Field

class Request(BaseModel):
    user: str | None = None
    url: str | None = None
    method: str | None = None
    headers: dict[str, Any] = Field(default_factory=dict)
    body: Any = None
    query_params: dict[str, Any] = Field(default_factory=dict)
    path_params: dict[str, Any] = Field(default_factory=dict)
```

### Task 3: Criar `shared/presentation/http/response.py`
```python
from typing import Any
from pydantic import BaseModel, Field

class Response(BaseModel):
    status_code: int
    body: Any = None
    headers: dict[str, Any] = Field(default_factory=dict)
```

### Task 4: Criar `shared/presentation/http/types.py`
```python
from typing import Callable, Coroutine, Any, TypeAlias
from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response

HttpHandler: TypeAlias = Callable[[Request], Coroutine[Any, Any, Response]]
```

### Task 5: Criar `shared/presentation/http/adapter.py`
- `request_adapter(request: FastAPIRequest, controller: HttpHandler) -> Response`
  - Extrai body, headers, query_params, path_params, url, method do FastAPIRequest
  - Cria `shared Request`
  - Chama `controller(http_request)`
- `response_adapter(response: Response) -> JSONResponse`
  - Converte `shared Response` para `JSONResponse`

### Task 6: Criar `shared/infra/config/interface/unit_of_work.py`
```python
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession

class UnitOfWork(ABC):
    @property
    @abstractmethod
    def session(self) -> AsyncSession: ...
    @abstractmethod
    async def commit(self) -> None: ...
    @abstractmethod
    async def rollback(self) -> None: ...
    @abstractmethod
    async def __aenter__(self): ...
    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb): ...
```

### Task 7: Criar `shared/infra/database/postgres_unit_of_work.py`
- `PostgresUnitOfWork(UnitOfWork)` com `async_sessionmaker`
- `__aenter__`: cria sessão, retorna self
- `__aexit__`: commita se sem exceção, rollback se com exceção, fecha sessão

### Task 8: Criar `shared/application/transactional_handler.py`
```python
class TransactionalHandler:
    def __init__(self, uow: UnitOfWork, handler: HttpHandler): ...
    async def __call__(self, request: Request) -> Response:
        async with self._uow:
            return await self._handler(request)
```

### Task 9: Adaptar `shared/presentation/responses.py`
- Manter `ok()`, `created()`, `error()` como helpers internos para `response_adapter`
- Ou remover — cada controller monta `Response` diretamente com o body padronizado

### Task 10: Verificar imports
- Ajustar `from shared...` → `from src.shared...` conforme convention do projeto
- Garantir que nenhum import ciclico seja criado

## Acceptance Criteria

- [ ] `shared.presentation.interface.controller.Controller` importável e funcional
- [ ] `shared.presentation.http.request.Request` importável e funcional
- [ ] `shared.presentation.http.response.Response` importável e funcional
- [ ] `shared.presentation.http.adapter.request_adapter` + `response_adapter` importáveis
- [ ] `shared.application.transactional_handler.TransactionalHandler` importável
- [ ] `shared.infra.config.interface.unit_of_work.UnitOfWork` importável
- [ ] `shared.infra.database.postgres_unit_of_work.PostgresUnitOfWork` importável
- [ ] `ruff check` no módulo shared passa sem erros novos
- [ ] `pyright` no módulo shared passa sem erros novos
