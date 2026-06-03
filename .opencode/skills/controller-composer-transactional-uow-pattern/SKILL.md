---
name: controller-composer-transactional-uow-pattern
description: Defines the standard backend flow for FastAPI routes, request/response adapters, independent controllers, composers per use case, UnitOfWork-based transactions, and reusable worker/event handlers.
---

# Controller, Composer, Adapter and UnitOfWork Pattern

## Objective

Define the standard backend flow for all controllers, routes, composers, transactions and use case wiring.

The final rule is:

```txt
FastAPI route
→ request_adapter
→ shared Request
→ composer
→ TransactionalHandler
→ Controller.handle(request)
→ UseCase.execute(...)
→ Repositories through UnitOfWork
→ shared Response
→ response_adapter
→ FastAPI response
```

## Main rule

Controllers must be completely independent from FastAPI.

Controllers do not import:

```txt
APIRouter
Depends
FastAPI Request
JSONResponse
HTTPException
FastAPI status
SQLAlchemy session
```

Controllers receive only:

```txt
shared.presentation.http.Request
```

Controllers return only:

```txt
shared.presentation.http.Response
```

## Why this pattern is required

The previous controller style mixed too many responsibilities:

```txt
FastAPI route
dependency injection
repository creation
use case creation
request validation
business orchestration
response mapping
transaction management
error formatting
```

This creates bugs like:

```txt
wrong DTO passed to mapper
entity treated as Pydantic model
model_dump called on domain entity
created_at/updated_at null
commit/rollback scattered
FastAPI coupled to business logic
workers using a different execution flow than HTTP
```

This pattern fixes that by making every entry point use the same execution contract.

## Final responsibility split

```txt
Route
- receives FastAPI request
- calls request_adapter
- calls composed handler
- converts shared Response to FastAPI response

Adapter
- converts FastAPI request into shared Request
- converts shared Response into FastAPI/JSON response

Controller
- validates request body/path/query at application boundary
- calls one use case
- returns shared Response
- does not know FastAPI
- does not know SQLAlchemy

Composer
- builds UnitOfWork
- builds repositories
- builds use case
- builds controller
- wraps controller with TransactionalHandler

TransactionalHandler
- opens UnitOfWork
- calls controller.handle
- commits if success
- rolls back if exception
- returns Response

UnitOfWork
- owns session lifecycle
- owns transaction lifecycle
- provides session to repositories
- commits/rolls back

Repository
- receives UnitOfWork or session
- performs persistence
- never commits
- never rollbacks

Use case
- executes business/application logic
- uses repositories
- may write outbox/inbox
- does not know FastAPI
```

## UnitOfWork and SessionManager

In this project, the UnitOfWork is the transaction/session manager.

The old `SessionManager` concept should be replaced by, or wrapped inside, a `UnitOfWork`.

The final project-level abstraction must be:

```txt
UnitOfWork
```

The UnitOfWork may internally use the same logic as the old SessionManager.

The external contract should be:

```python
async with uow:
    ...
```

The UnitOfWork must expose the active session for repositories.

## Shared folder structure

Create or standardize:

```txt
src/shared/
  presentation/
    interface/
      controller.py

    http/
      request.py
      response.py
      adapter.py
      types.py

  application/
    transactional_handler.py
    http_handler.py

  infra/
    config/
      interface/
        unit_of_work.py
```

## Request object

Create:

```txt
src/shared/presentation/http/request.py
```

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

## Response object

Create:

```txt
src/shared/presentation/http/response.py
```

```python
from typing import Any
from pydantic import BaseModel, Field


class Response(BaseModel):
    status_code: int
    body: Any = None
    headers: dict[str, Any] = Field(default_factory=dict)
```

## HttpHandler type

Create:

```txt
src/shared/presentation/http/types.py
```

```python
from typing import Callable, Coroutine, Any, TypeAlias

from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response


HttpHandler: TypeAlias = Callable[[Request], Coroutine[Any, Any, Response]]
```

If the project import root does not use `src.`, adapt imports consistently.

## Controller interface

Create:

```txt
src/shared/presentation/interface/controller.py
```

```python
from abc import ABC, abstractmethod

from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response


class Controller(ABC):
    @abstractmethod
    async def handle(self, request: Request) -> Response:
        ...
```

## TransactionalHandler

Create:

```txt
src/shared/application/transactional_handler.py
```

```python
from src.shared.presentation.http.types import HttpHandler
from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response
from src.shared.infra.config.interface.unit_of_work import UnitOfWork


class TransactionalHandler:
    def __init__(self, uow: UnitOfWork, handler: HttpHandler):
        self._uow = uow
        self._handler = handler

    async def __call__(self, request: Request) -> Response:
        async with self._uow:
            return await self._handler(request)
```

Rule:

```txt
All controllers must be executed through TransactionalHandler.
```

This applies to:

```txt
HTTP routes
workers
outbox handlers
inbox handlers
dispatchers
scripts that execute use cases
```

## UnitOfWork interface

Create:

```txt
src/shared/infra/config/interface/unit_of_work.py
```

```python
from abc import ABC, abstractmethod
from sqlalchemy.ext.asyncio import AsyncSession


class UnitOfWork(ABC):
    @property
    @abstractmethod
    def session(self) -> AsyncSession:
        ...

    @abstractmethod
    async def commit(self) -> None:
        ...

    @abstractmethod
    async def rollback(self) -> None:
        ...

    @abstractmethod
    async def __aenter__(self):
        ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc, tb):
        ...
```

## PostgreSQL UnitOfWork

Recommended for MVP:

```txt
src/shared/infra/database/postgres_unit_of_work.py
```

```python
from typing import Self, Optional
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker

from src.shared.infra.config.interface.unit_of_work import UnitOfWork


class PostgresUnitOfWork(UnitOfWork):
    def __init__(self, async_engine: AsyncEngine) -> None:
        self._async_engine = async_engine
        self._session: Optional[AsyncSession] = None

    @property
    def session(self) -> AsyncSession:
        if self._session:
            return self._session
        raise RuntimeError("UnitOfWork not started")

    async def commit(self) -> None:
        if not self._session:
            raise RuntimeError("UnitOfWork not started")
        await self._session.commit()

    async def rollback(self) -> None:
        if not self._session:
            raise RuntimeError("UnitOfWork not started")
        await self._session.rollback()

    async def __aenter__(self) -> Self:
        session_factory = async_sessionmaker(
            bind=self._async_engine,
            expire_on_commit=False,
            class_=AsyncSession,
        )
        self._session = session_factory()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        try:
            if exc_type:
                await self.rollback()
            else:
                await self.commit()
        finally:
            if self._session:
                await self._session.close()
            self._session = None
```

## Request adapter

Create:

```txt
src/shared/presentation/http/adapter.py
```

```python
from fastapi import Request as FastAPIRequest
from fastapi.responses import JSONResponse

from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response
from src.shared.presentation.http.types import HttpHandler


async def request_adapter(
    request: FastAPIRequest,
    controller: HttpHandler,
) -> Response:
    if hasattr(request.state, "body") and request.state.body is not None:
        body = request.state.body
    else:
        try:
            body = await request.json()
        except Exception:
            body = None

    http_request = Request(
        body=body,
        headers=dict(request.headers),
        query_params=dict(request.query_params),
        path_params=dict(request.path_params),
        url=str(request.url),
        method=request.method,
    )

    return await controller(http_request)


def response_adapter(response: Response) -> JSONResponse:
    return JSONResponse(
        status_code=response.status_code,
        content=response.body,
        headers=response.headers,
    )
```

## Route pattern

Routes must be minimal.

```python
from fastapi import APIRouter, Request as FastAPIRequest

from src.shared.presentation.http.adapter import request_adapter, response_adapter
from src.modules.billing.application.composers.activate_plan_composer import (
    activate_plan_composer,
)


router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/plans/{plan_id}/activate")
async def activate_plan(request: FastAPIRequest):
    handler = activate_plan_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
```

Rules:

```txt
Route does not instantiate repositories.
Route does not instantiate use cases.
Route does not call SQLAlchemy.
Route does not create DTOs.
Route does not return domain entities.
Route does not contain business validation.
Route does not catch business exceptions unless globally required.
```

## Controller pattern

Controller receives `Request` and returns `Response`.

```python
from src.shared.presentation.interface.controller import Controller
from src.shared.presentation.http.request import Request
from src.shared.presentation.http.response import Response
from src.modules.billing.service.use_cases.activate_plan_use_case import (
    ActivatePlanUseCase,
)
from src.shared.entity.inbox import Inbox as InboxEntity
from src.modules.billing.domain.events.plan_events import PlanActivatedEventPayload


class ActivatePlanController(Controller):
    def __init__(self, activate_plan_use_case: ActivatePlanUseCase):
        self._activate_plan_use_case = activate_plan_use_case

    async def handle(self, request: Request) -> Response:
        body = request.body if isinstance(request.body, dict) else {}

        inbox_data = body.get("inbox")
        if not inbox_data:
            return Response(
                status_code=400,
                body={"success": False, "message": "Inbox is required", "data": None},
            )

        try:
            if isinstance(inbox_data, dict):
                inbox = InboxEntity(**inbox_data)
            elif isinstance(inbox_data, InboxEntity):
                inbox = inbox_data
            else:
                return Response(
                    status_code=400,
                    body={"success": False, "message": "Invalid inbox format", "data": None},
                )
        except (KeyError, ValueError, TypeError) as e:
            return Response(
                status_code=400,
                body={"success": False, "message": f"Invalid inbox data: {str(e)}", "data": None},
            )

        payload = inbox.payload
        if not payload or not isinstance(payload, dict):
            return Response(
                status_code=400,
                body={
                    "success": False,
                    "message": "Inbox payload is required and must be a dict",
                    "data": None,
                },
            )

        try:
            event_payload = PlanActivatedEventPayload(**payload)
        except (ValueError, TypeError) as e:
            return Response(
                status_code=400,
                body={"success": False, "message": f"Invalid payload data: {str(e)}", "data": None},
            )

        await self._activate_plan_use_case.execute(
            plan_id=str(event_payload.id),
            inbox=inbox,
        )

        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "Plan activated successfully",
                "data": None,
            },
        )
```

## Composer pattern

Each use case must have a composer.

```txt
src/modules/billing/application/composers/activate_plan_composer.py
```

```python
from src.shared.application.transactional_handler import TransactionalHandler
from src.shared.infra.database.engine import engine
from src.shared.infra.database.postgres_unit_of_work import PostgresUnitOfWork

from src.modules.billing.infra.repositories import (
    PlanRepository,
    OutboxRepository,
    InboxRepository,
)
from src.modules.billing.service.use_cases.activate_plan_use_case import (
    ActivatePlanUseCase,
)
from src.modules.billing.presentation.controllers.activate_plan_controller import (
    ActivatePlanController,
)


def activate_plan_composer() -> TransactionalHandler:
    uow = PostgresUnitOfWork(engine)

    plan_repository = PlanRepository(uow)
    outbox_repository = OutboxRepository(uow)
    inbox_repository = InboxRepository(uow)

    activate_plan_use_case = ActivatePlanUseCase(
        plan_repository=plan_repository,
        outbox_repository=outbox_repository,
        inbox_repository=inbox_repository,
    )

    activate_plan_controller = ActivatePlanController(
        activate_plan_use_case=activate_plan_use_case,
    )

    return TransactionalHandler(
        uow=uow,
        handler=activate_plan_controller.handle,
    )
```

Rules:

```txt
One composer per use case.
Composer is the only place that wires concrete dependencies.
Composer returns TransactionalHandler.
Composer does not execute business logic.
Composer does not call controller directly.
Composer does not open transaction directly.
```

## Repository with UnitOfWork

Repositories should receive UnitOfWork.

```python
from src.shared.infra.config.interface.unit_of_work import UnitOfWork


class PlanRepository:
    def __init__(self, uow: UnitOfWork):
        self._uow = uow

    @property
    def session(self):
        return self._uow.session
```

Rules:

```txt
Repository does not create session.
Repository does not commit.
Repository does not rollback.
Repository can flush/refresh when needed.
Repository uses uow.session.
```

## Use case pattern

Use case receives repositories and executes the application rule.

```python
class ActivatePlanUseCase:
    def __init__(
        self,
        plan_repository,
        outbox_repository,
        inbox_repository,
    ):
        self._plan_repository = plan_repository
        self._outbox_repository = outbox_repository
        self._inbox_repository = inbox_repository

    async def execute(self, plan_id: str, inbox):
        plan = await self._plan_repository.get(plan_id)

        plan.activate()

        await self._plan_repository.update(plan)
        await self._inbox_repository.mark_as_processed(inbox.id)

        return plan
```

Rules:

```txt
Use case does not commit.
Use case does not rollback.
Use case does not import FastAPI.
Use case does not create repository.
Use case does not know HTTP.
Use case may emit outbox events.
Use case may process inbox events.
```

## Inbox/Outbox with same flow

Workers must use the same controller/composer/TransactionalHandler flow.

Worker flow:

```txt
worker receives inbox event
→ creates Request(body={"inbox": inbox})
→ gets composed handler
→ calls handler(request)
→ TransactionalHandler opens UoW
→ Controller validates inbox and payload
→ UseCase executes
→ UoW commits/rollbacks
```

Example:

```python
from src.shared.presentation.http.request import Request
from src.modules.billing.application.composers.activate_plan_composer import (
    activate_plan_composer,
)


async def handle_plan_activated(inbox):
    handler = activate_plan_composer()
    request = Request(body={"inbox": inbox})
    response = await handler(request)

    if response.status_code >= 400:
        raise RuntimeError(response.body.get("message", "Handler failed"))
```

## Standard response body

Success:

```python
{
    "success": True,
    "message": "Operation completed successfully",
    "data": ...
}
```

Error:

```python
{
    "success": False,
    "message": "Error message",
    "data": None,
}
```

Validation error:

```python
{
    "success": False,
    "message": "Validation error",
    "data": [...]
}
```

## Controller validation

Controller can validate application boundary input.

Controller can check:

```txt
missing body
invalid body format
missing path param
invalid UUID
invalid inbox
invalid event payload
missing required field
```

Controller should not contain deep business rules.

Business rules stay in use cases/domain.

## Mapping rule

Presentation mapping must be explicit.

Use:

```txt
domain entity → Response body/schema
```

Avoid:

```txt
entity.model_dump()
CreateOutput passed to entity mapper
SQLAlchemy model returned directly
```

If using response schemas, create presentation mappers:

```txt
src/modules/<module>/presentation/mappers.py
```

## Error handling

Controller should return controlled `Response` for expected validation errors.

Unexpected exceptions should bubble to `TransactionalHandler`/global exception handler so UnitOfWork rolls back.

Rules:

```txt
Expected bad input → Response 400/422
Not found → Response 404
Unauthorized → Response 401
Forbidden → Response 403
Unexpected exception → raise
```

Do not swallow unexpected exceptions silently.

## Transaction rule

All controllers use TransactionalHandler.

Even read-only controllers.

Reason:

```txt
single execution pattern
consistent dependency wiring
no special cases
simple mental model for AI-generated code
```

Optimization can happen later.

## Migration plan from current controllers

Migration steps per endpoint:

```txt
1. Identify current route function.
2. Extract request validation into a Controller class.
3. Extract dependency wiring into composer.
4. Move repository/use case instantiation to composer.
5. Route calls request_adapter + composer.
6. Add response_adapter.
7. Remove Depends(get_session_manager) from route.
8. Remove repository creation from route.
9. Remove use case creation from route.
10. Ensure controller returns shared Response.
11. Add tests for route behavior.
```

## Example migration: identity list organizations

Old style:

```python
@router.get("/organizations")
async def list_organizations(manager=Depends(get_session_manager)):
    repo = SQLAlchemyOrganizationRepository(manager.session)
    orgs = await repo.list_all()
    return ok([...])
```

New route:

```python
@router.get("/organizations")
async def list_organizations(request: FastAPIRequest):
    handler = list_organizations_composer()
    response = await request_adapter(request, handler)
    return response_adapter(response)
```

New controller:

```python
class ListOrganizationsController(Controller):
    def __init__(self, use_case):
        self._use_case = use_case

    async def handle(self, request: Request) -> Response:
        organizations = await self._use_case.execute()

        return Response(
            status_code=200,
            body={
                "success": True,
                "message": "Organizations listed successfully",
                "data": [organization_to_response(org) for org in organizations],
            },
        )
```

New composer:

```python
def list_organizations_composer() -> TransactionalHandler:
    uow = PostgresUnitOfWork(engine)
    repository = SQLAlchemyOrganizationRepository(uow)
    use_case = ListOrganizationsUseCase(repository)
    controller = ListOrganizationsController(use_case)
    return TransactionalHandler(uow, controller.handle)
```

## Tests required

For each migrated endpoint:

```txt
route returns same status code as before
route returns same response shape
controller can be tested without FastAPI
controller handles invalid body
composer builds handler successfully
transaction commits on success
transaction rolls back on exception
repository does not commit
route does not instantiate repository
route does not use Depends(get_session_manager)
```

## Forbidden patterns

Do not use in route files:

```txt
Depends(get_session_manager)
SQLAlchemyRepository(...)
UseCase(...)
manager.session
session.commit()
session.rollback()
model_dump() on entities
business validation
```

Do not use in controllers:

```txt
FastAPI imports
APIRouter
Depends
JSONResponse
SQLAlchemy session
repository instantiation
UnitOfWork instantiation
```

Do not use in repositories:

```txt
commit
rollback
close session
create new session
```

## Accepted patterns

Routes:

```txt
FastAPIRequest
request_adapter
response_adapter
composer
```

Controllers:

```txt
Request
Response
UseCase
input validation
presentation mapping
```

Composers:

```txt
UnitOfWork
repositories
use cases
controllers
TransactionalHandler
```

Use cases:

```txt
repositories
entities
domain services
outbox/inbox repositories
```

Repositories:

```txt
uow.session
SQLAlchemy
mappers
flush/refresh when needed
```

## Final project rule

Every endpoint and worker handler must follow the same execution shape:

```txt
Input adapter
→ TransactionalHandler
→ Controller
→ UseCase
→ Repository through UnitOfWork
→ Response
```

This rule exists to make the project stable, testable and safe for AI-generated code.
