from __future__ import annotations

from modules.agent.infra.adapters.tool_executor import HttpToolExecutor

_shared_executor: HttpToolExecutor | None = None


def configure_http_tool_executor(executor: HttpToolExecutor) -> None:
    global _shared_executor
    _shared_executor = executor


def get_http_tool_executor() -> HttpToolExecutor:
    if _shared_executor is None:
        raise RuntimeError("HTTP tool executor is not configured")
    return _shared_executor


async def close_http_tool_executor() -> None:
    global _shared_executor
    if _shared_executor is not None:
        await _shared_executor.aclose()
        _shared_executor = None
