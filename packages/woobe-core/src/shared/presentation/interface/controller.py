from abc import ABC, abstractmethod

from shared.presentation.contracts import OperationRequest, OperationResult


class Controller(ABC):
    @abstractmethod
    async def handle(self, request: OperationRequest) -> OperationResult: ...
