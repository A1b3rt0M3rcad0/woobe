from abc import ABC, abstractmethod
from typing import Any


class OutboxEventWriter(ABC):
    @abstractmethod
    async def write(self, *args: Any, **kwargs: Any) -> None: ...
