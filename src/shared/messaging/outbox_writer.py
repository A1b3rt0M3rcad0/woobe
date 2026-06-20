from typing import Any, Protocol


class OutboxEventWriter(Protocol):
    async def write(self, event: Any) -> None:
        ...
