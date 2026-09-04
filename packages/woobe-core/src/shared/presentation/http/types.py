from typing import Any, Callable, Coroutine

from shared.presentation.contracts import OperationRequest
from shared.presentation.contracts import OperationResult

HttpHandler: Callable[[OperationRequest], Coroutine[Any, Any, OperationResult]]

