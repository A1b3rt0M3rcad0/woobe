# Repository Refactoring Skill

## Purpose

Use this skill when refactoring repositories in a Python backend that uses SQLAlchemy async, DDD/Clean Architecture, domain entities, ORM models, mappers, Unit of Work, Outbox, and cursor-based pagination.

The goal is to standardize repository architecture across all modules, not only a single module.

The central rule is:

> `BaseSQLAlchemyRepository` must contain only reusable technical infrastructure.
>
> Specific repositories must implement domain-facing contracts, own aggregate-specific queries, and return domain entities or `CursorPage[Entity]`.

---

## Scope

This refactoring must be applied globally.

Before changing code, inspect all modules and repository implementations.

Search for:

```text
Repository
Repositories
BaseRepository
SQLAlchemyRepository
SQLAlchemy*Repository
repository.py
repositories.py
infra/repositories
domain/repositories
application/repositories
CursorPage
pagination
UnitOfWork
Outbox
```

Do not assume the first repository found represents the whole project. Build a project-wide inventory first.

Inspect at minimum:

```text
modules/*
shared/*
```

When the project has a different structure, adapt the search accordingly.

---

## Architectural Boundaries

### Domain repository contracts

Domain repository contracts must be expressed in domain language.

They may depend on:

```text
Domain entities
Value objects
UUID
Primitive types
CursorPage
ABC or Protocol
```

They must not depend on:

```text
SQLAlchemy
AsyncSession
BaseModel
ORM models
select()
database-specific expressions
infrastructure mappers
```

Correct:

```python
class UserRepository(ABC):
    @abstractmethod
    async def get_by_id(self, user_id: UUID) -> User | None: ...

    @abstractmethod
    async def get_by_email(self, email: str) -> User | None: ...
```

Incorrect:

```python
class UserRepository(ABC):
    async def get_by_id(self, user_id: UUID) -> UserModel | None: ...
```

---

## Base Repository Rule

The base repository must be a technical SQLAlchemy abstraction.

It must not be treated as a domain repository.

Prefer this name:

```python
BaseSQLAlchemyRepository
```

Avoid generic names such as:

```python
BaseRepository
```

unless the project already has strong naming conventions and changing the name would cause unnecessary churn.

The base class works with ORM models only. It must not know domain entities or mappers.

---

## Required Base Repository Shape

A good base repository should look conceptually like this:

```python
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.database.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseSQLAlchemyRepository(Generic[T]):
    def __init__(self, session: AsyncSession, model_cls: type[T]) -> None:
        self._session = session
        self._model_cls = model_cls

    async def _add_model(self, model: T) -> T:
        self._session.add(model)
        return model

    async def _get_model_by_id(self, id: UUID) -> T | None:
        return await self._session.get(self._model_cls, id)

    async def _delete_model(self, model: T) -> None:
        await self._session.delete(model)

    async def _flush(self) -> None:
        await self._session.flush()

    async def _refresh_model(self, model: T) -> None:
        await self._session.refresh(model)
```

Adapt imports and names to the actual project.

The methods are intentionally protected. They are implementation primitives, not domain API.

---

## Public Method Collision Rule

Do not expose public methods in the base repository when their names collide semantically with domain repository methods but return different types.

Problematic:

```python
class BaseRepository(Generic[T]):
    async def get_by_id(self, id: UUID) -> T | None:
        ...
```

while the domain contract says:

```python
class UserRepository(ABC):
    async def get_by_id(self, user_id: UUID) -> User | None:
        ...
```

This creates ambiguity:

```text
BaseRepository.get_by_id -> ORM model
UserRepository.get_by_id -> domain entity
```

Preferred:

```python
async def _get_model_by_id(self, id: UUID) -> T | None:
    ...
```

Then the concrete repository maps the model to the entity:

```python
async def get_by_id(self, user_id: UUID) -> User | None:
    model = await self._get_model_by_id(user_id)
    return user_model_to_entity(model) if model else None
```

---

## Prohibition: list_all

Do not use, create, or preserve `list_all()` as a public generic method.

Remove this pattern:

```python
async def list_all(self) -> list[T]:
    result = await self.session.execute(select(self.model_cls))
    return list(result.scalars().all())
```

Reason:

```text
list_all ignores pagination, tenant scope, permissions, filters, soft delete, ordering, indexing, and query cost.
```

If a list can grow, it must be explicit and paginated.

---

## CursorPage

The project uses cursor-based pagination through a structure similar to:

```python
from typing import Generic, TypeVar

T = TypeVar("T")


class CursorPage(Generic[T]):
    def __init__(
        self,
        items: list[T],
        cursor: str | None = None,
        next_cursor: str | None = None,
        has_next: bool = False,
        total: int | None = None,
    ) -> None:
        self.items = items
        self.cursor = cursor
        self.next_cursor = next_cursor
        self.has_next = has_next
        self.total = total
```

Before implementing pagination, locate the real `CursorPage` class.

Do not duplicate it.

Search for:

```text
CursorPage
cursor
next_cursor
has_next
pagination
paginate
```

---

## Pagination Investigation Checklist

Before changing pagination, identify:

```text
Where CursorPage is defined
How cursors are encoded
How cursors are decoded
Whether a pagination helper already exists
Whether cursor uses id, created_at, ULID, UUIDv7, offset, base64/json, or another format
Whether ordering is ascending or descending
Whether total is supported
Whether total is required or optional
Which repositories already use CursorPage
Which repositories still return list[T]
Which use cases consume those methods
Which tests cover pagination
```

Do not invent a new cursor convention if one already exists.

---

## Pagination Rules

All repository pagination must obey:

1. Do not use `list_all`.
2. Do not return unlimited lists for data that can grow.
3. Use `CursorPage[T]`.
4. Apply explicit ordering.
5. Ensure ordering is deterministic.
6. Fetch `limit + 1` rows to compute `has_next`.
7. Return only `limit` items.
8. Compute `next_cursor` from the last returned item, not from the extra row.
9. Do not expose ORM models in domain-facing `CursorPage`.
10. Allow `total=None` when counting is expensive or unnecessary.
11. Validate `limit`.
12. Avoid unstable cursors.
13. Avoid pagination without an index-compatible ordering.
14. Handle ordering ties deterministically.

---

## Recommended Cursor Strategy

If the project has no existing convention, prefer:

```text
created_at + id
```

when both columns exist.

Use `id` alone only when it is ordered or monotonic, for example:

```text
ULID
UUIDv7
Snowflake ID
sequential integer
```

Do not use UUIDv4 as temporal ordering. UUIDv4 is random and does not represent creation order.

Avoid offset pagination for large datasets.

---

## Base Pagination Primitive

The base SQLAlchemy repository may provide a protected pagination primitive.

Conceptual shape:

```python
async def _paginate_models(
    self,
    statement,
    *,
    limit: int,
    cursor: str | None = None,
    # use the project's real cursor convention
) -> CursorPage[T]:
    ...
```

The implementation must follow the actual project conventions.

The base pagination primitive returns `CursorPage[Model]`.

The concrete repository must convert it to `CursorPage[Entity]` before returning to application/domain code.

Example:

```python
page = await self._paginate_models(
    select(OrganizationMemberModel).where(
        OrganizationMemberModel.organization_id == organization_id
    ),
    limit=limit,
    cursor=cursor,
)

return CursorPage(
    items=[
        organization_member_model_to_entity(model)
        for model in page.items
    ],
    cursor=page.cursor,
    next_cursor=page.next_cursor,
    has_next=page.has_next,
    total=page.total,
)
```

Do not return `CursorPage[OrganizationMemberModel]` from a domain-facing repository method.

---

## Specific Repositories

Specific repositories implement domain contracts.

They should:

```text
Inherit from the domain repository interface
Optionally inherit from BaseSQLAlchemyRepository
Use ORM models internally
Use mappers entity <-> model
Own aggregate-specific queries
Return domain entities
Return CursorPage[Entity] for paginated methods
```

Example:

```python
class SQLAlchemyUserRepository(
    BaseSQLAlchemyRepository[UserModel],
    UserRepository,
):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, UserModel)

    async def save(self, user: User) -> User:
        model = user_entity_to_model(user)
        await self._add_model(model)
        await self._flush()
        return user_model_to_entity(model)

    async def get_by_id(self, user_id: UUID) -> User | None:
        model = await self._get_model_by_id(user_id)
        return user_model_to_entity(model) if model else None

    async def get_by_email(self, email: str) -> User | None:
        result = await self._session.execute(
            select(UserModel).where(UserModel.email == email)
        )
        model = result.scalar_one_or_none()
        return user_model_to_entity(model) if model else None

    async def delete(self, user_id: UUID) -> None:
        model = await self._get_model_by_id(user_id)
        if model:
            await self._delete_model(model)
```

---

## Query Placement

Aggregate-specific queries belong in specific repositories.

Examples:

```text
get_by_email
get_by_slug
get_by_organization_and_user
get_by_organization_and_email
list_by_user
list_by_organization
paginate_by_user
paginate_by_organization
```

Do not move aggregate-specific query logic into the base repository.

The base repository should not know about:

```text
email
slug
organization_id
user_id
status
tenant
business-specific filters
```

unless these are part of a deliberate shared technical mechanism, such as tenant scoping infrastructure.

---

## List Method Migration

When a method currently returns `list[T]`, decide whether to migrate it to `CursorPage[T]`.

Current:

```python
async def list_by_user(self, user_id: UUID) -> list[UserSession]: ...
```

Preferred when the result can grow:

```python
async def list_by_user(
    self,
    user_id: UUID,
    *,
    limit: int,
    cursor: str | None = None,
) -> CursorPage[UserSession]: ...
```

Do not change signatures blindly.

First inspect all consumers:

```text
use cases
application services
handlers
controllers
tests
CLI jobs
background workers
```

Migration options:

### Option A: Direct Migration

Use when impact is small and contained.

```python
async def list_by_user(
    self,
    user_id: UUID,
    *,
    limit: int,
    cursor: str | None = None,
) -> CursorPage[UserSession]: ...
```

### Option B: Add Paginated Method, Keep Old Method Temporarily

Use when impact is large.

```python
async def list_by_user(self, user_id: UUID) -> list[UserSession]: ...

async def paginate_by_user(
    self,
    user_id: UUID,
    *,
    limit: int,
    cursor: str | None = None,
) -> CursorPage[UserSession]: ...
```

### Option C: Two-Phase Migration

Phase 1:

```text
Add paginated methods
Keep old list methods
Update new use cases to use pagination
Mark old list methods for removal
```

Phase 2:

```text
Update remaining consumers
Remove old methods
Update tests
```

Choose based on actual project impact.

---

## Save Semantics

Audit all `save()` methods.

Determine whether `save()` means:

```text
insert only
```

or:

```text
insert or update
```

If current `save()` does this:

```python
model = entity_to_model(entity)
self._session.add(model)
await self._flush()
```

then it may only be safe for inserts.

Risk:

```text
If entity already exists, creating a new model and calling add may cause primary key conflicts or incorrect session behavior.
```

Acceptable strategies:

### Strategy A: Separate add/update

```python
async def add(self, entity: Entity) -> Entity: ...
async def update(self, entity: Entity) -> Entity: ...
```

Use when domain semantics distinguish creation and mutation.

### Strategy B: Controlled upsert

```text
Find model by ID
If found, update fields on existing model
If not found, create and add model
Flush
Map model back to entity
```

Use when `save()` is intended to persist current entity state.

### Strategy C: session.merge

```python
model = await self._session.merge(entity_to_model(entity))
await self._flush()
return model_to_entity(model)
```

Trade-offs:

```text
Simple
May issue extra queries
Can hide create/update semantics
Needs testing with detached entities
May be inappropriate for strict invariants
```

Do not change `save()` semantics without inspecting use cases and tests.

If uncertain, preserve current behavior and document the risk.

---

## Flush, Refresh, Commit

Repositories may call:

```text
flush
refresh
```

Repositories must not call:

```text
commit
rollback
```

Transaction boundaries belong to:

```text
UnitOfWork
application service
request/session dependency
transaction manager
```

Rules:

1. Use `flush()` when the repository needs database-side state materialized.
2. Use `refresh()` when returned entities depend on database-generated fields.
3. Avoid unnecessary `refresh()`.
4. Standardize inconsistent `refresh()` usage if justified.
5. Never introduce `commit()` inside repositories.

Audit all repositories for accidental commits.

---

## Outbox

Locate all outbox/event writer implementations.

A transactional outbox writer should add events to the same database session:

```python
class SQLAlchemyOutboxEventWriter(OutboxEventWriter):
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(...):
        event = OutboxEventModel(...)
        self._session.add(event)
```

Rules:

1. Do not commit inside the writer.
2. Preserve transactional outbox behavior.
3. Preserve `aggregate_type`.
4. Preserve `aggregate_id`.
5. Preserve `event_type`.
6. Preserve `payload`.
7. Preserve `correlation_id`.
8. Preserve `causation_id`.
9. Do not merge outbox writing into aggregate repositories unless the project deliberately uses that pattern.

---

## ABC vs Protocol

Do not refactor `ABC` to `Protocol` as part of this task unless there is a clear, low-risk reason.

Both are acceptable.

Use this decision rule:

```text
ABC: explicit nominal contracts and runtime enforcement.
Protocol: structural typing and lower nominal coupling.
```

The priority is not ABC vs Protocol.

The priority is repository boundary correctness, base repository cleanup, and cursor pagination.

---

## Heredity and Composition

This is acceptable:

```python
class SQLAlchemyUserRepository(
    BaseSQLAlchemyRepository[UserModel],
    UserRepository,
):
    ...
```

only if the base repository exposes protected technical methods and does not pretend to implement the domain contract.

Avoid this pattern:

```python
class SQLAlchemyUserRepository(
    BaseRepository[UserModel],
    UserRepository,
):
    ...
```

when `BaseRepository` exposes public methods such as `get_by_id`, `delete`, or `list_all` that operate on models.

If multiple inheritance creates ambiguity in a specific module, consider composition:

```python
class SQLAlchemyUserRepository(UserRepository):
    def __init__(self, session: AsyncSession) -> None:
        self._base = BaseSQLAlchemyRepository(session, UserModel)
```

Do not switch globally to composition unless it materially improves clarity and reduces risk.

---

## Mappers

Mappers belong to infrastructure.

Concrete SQLAlchemy repositories may call:

```text
entity_to_model
model_to_entity
```

The base SQLAlchemy repository must not know mappers.

The domain layer must not import mappers.

Correct layering:

```text
Domain contract -> entities only
Infrastructure repository -> ORM models + mappers
Base SQLAlchemy repository -> ORM models only
```

---

## Global Refactoring Procedure

### Step 1: Inventory

Create an inventory of all repositories across all modules.

For each repository, record:

```text
Module
Domain interface
Concrete implementation
Base class usage
ORM model
Domain entity
Mapper functions
List methods
Pagination usage
Save semantics
Flush/refresh usage
Commit usage
Outbox interaction
Tests
Consumers
```

### Step 2: Diagnose

Identify:

```text
Public base methods with domain-like names
Methods returning ORM models through domain-facing APIs
list_all usage
Unpaginated large list methods
Repository-specific queries in shared base
SQLAlchemy imports in domain contracts
Domain imports in base repository
Inconsistent save semantics
Inconsistent flush/refresh
Commits inside repositories
CursorPage misuse
Missing deterministic ordering
```

### Step 3: Design Target

Define the target repository pattern for the project:

```text
BaseSQLAlchemyRepository with protected technical methods
Concrete SQLAlchemy repositories implementing domain contracts
CursorPage-based pagination for growing lists
No list_all
No commits in repositories
Mappers only in concrete infrastructure repositories
```

### Step 4: Refactor Incrementally

Apply changes in a safe order:

1. Create `BaseSQLAlchemyRepository`.
2. Move technical base methods to protected names.
3. Remove `list_all`.
4. Add or reuse protected pagination helper.
5. Update concrete repositories to use protected methods.
6. Update imports.
7. Update list methods to use `CursorPage` where appropriate.
8. Update consumers if signatures change.
9. Update tests.
10. Remove obsolete base class or compatibility layer if safe.

### Step 5: Validate

Run available project commands.

Examples:

```bash
pytest
mypy
pyright
ruff check
ruff format
```

Use the actual commands defined by the project.

Also verify manually:

```text
No SQLAlchemy imports in domain repositories
No ORM models returned by domain-facing repositories
No list_all remains
No repository commits
No broken imports
No circular imports
All paginated methods return CursorPage[Entity]
All pagination has deterministic order
```

---

## Acceptance Criteria

The refactor is complete only when:

1. All modules were inspected.
2. All repositories were inventoried.
3. `BaseRepository` ambiguity was removed or justified.
4. Technical base methods are protected.
5. `list_all()` is removed.
6. `CursorPage` is used for growing list queries.
7. Domain contracts remain infrastructure-free.
8. Concrete repositories return domain entities.
9. ORM models do not leak outside infrastructure.
10. Pagination uses deterministic ordering.
11. `save()` semantics were audited.
12. `flush()` and `refresh()` usage was audited.
13. No `commit()` exists inside repositories.
14. Outbox behavior is preserved.
15. Tests/type checks/lint were run where available.
16. Remaining risks are documented.

---

## Final Report Format

After refactoring, produce a concise final report with:

```text
1. Repository inventory summary
2. Architectural diagnosis
3. Refactoring decisions
4. Files changed
5. Behavior preserved
6. Behavior intentionally changed
7. Pagination strategy used
8. Save semantics decision
9. Validation commands run
10. Remaining risks
11. Recommended follow-ups
```

Do not provide vague statements such as:

```text
Improved code quality.
Refactored repositories.
Cleaned architecture.
```

Be specific.

---

## Non-Negotiable Rules

Do not:

```text
Use list_all
Expose ORM models from domain-facing repositories
Import SQLAlchemy in domain repository contracts
Introduce commit inside repositories
Invent a new cursor scheme without checking existing conventions
Use unstable pagination
Refactor only one module and ignore others
Hide behavior changes
Remove methods without updating consumers
Duplicate CursorPage
Move mappers into the domain layer
Put domain entity logic into BaseSQLAlchemyRepository
```

Always:

```text
Study first
Refactor second
Validate third
Report precisely
```

---

## Core Principle

The base repository is infrastructure.

The specific repository is domain-facing.

Pagination is explicit.

List-all is forbidden.

Boundaries matter more than reducing a few lines of code.
