from typing import Any, Protocol


class UseCase(Protocol):
    async def execute(self, *args: Any, **kwargs: Any) -> Any: ...
