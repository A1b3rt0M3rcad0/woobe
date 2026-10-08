from typing import Protocol


class ReleaseTestExecutionStore(Protocol):
    async def prepare(self, request, principal): ...
    async def finish(self, test_id, *, actual_output, errors, latency_ms): ...


class ReleaseTestRuntime(Protocol):
    async def run(self, request, principal, test_id) -> dict: ...
