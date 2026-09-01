from abc import ABC, abstractmethod

from shared.presentation.http.request import Request
from shared.presentation.http.response import Response


class Controller(ABC):
    @abstractmethod
    async def handle(self, request: Request) -> Response: ...
