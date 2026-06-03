from abc import ABC, abstractmethod

from sqlalchemy.ext.asyncio import AsyncEngine


class BaseWorker(ABC):

    def __init__(self, async_engine: AsyncEngine) -> None:
        self._async_engine = async_engine

    @abstractmethod
    async def run(self) -> None:
        ...
