from typing import Any, Protocol, TypeVar


T = TypeVar("T")


class UseCase(Protocol[T]):
    async def execute(self, *args: Any, **kwargs: Any) -> T: ...
