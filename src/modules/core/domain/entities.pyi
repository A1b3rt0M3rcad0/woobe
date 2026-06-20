from datetime import datetime
from typing import Any
from uuid import UUID


def __getattr__(name: str) -> Any: ...


class Project:
    id: UUID
    organization_id: UUID
    name: str
    slug: str
    status: Any
    data: dict[str, Any]
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...


class ApiKey:
    id: UUID
    project_id: UUID
    created_at: datetime
    updated_at: datetime | None
    def __init__(self, **kwargs: Any) -> None: ...
