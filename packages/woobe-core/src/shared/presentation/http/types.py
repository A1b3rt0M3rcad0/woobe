from typing import Any, Callable, Coroutine

from shared.presentation.http.request import Request
from shared.presentation.http.response import Response

HttpHandler: Callable[[Request], Coroutine[Any, Any, Response]]
