from typing import Protocol
from contextvars import ContextVar

# Request-local evidence for the authorized test wrapper; never enabled by input metadata.
release_test_output_capture: ContextVar[dict | None] = ContextVar("release_test_output_capture", default=None)


class ReleaseTestExecutionStore(Protocol):
    async def prepare(self, request, principal): ...
    async def finish(self, test_id, *, actual_output, errors, latency_ms): ...


class ReleaseTestRuntime(Protocol):
    async def run(self, request, principal, test_id, *, snapshot=None) -> dict: ...
