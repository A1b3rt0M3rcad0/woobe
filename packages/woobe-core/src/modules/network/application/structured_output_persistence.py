from __future__ import annotations


def install_structured_output_persistence() -> None:
    from modules.network.application.runtime import NetworkExecutor

    if hasattr(NetworkExecutor, "_structured_output_base_execute"):
        return
    base_execute = NetworkExecutor.execute

    async def execute(self, execution, version):
        result = await base_execute(self, execution, version)
        persist = getattr(self._store, "persist_execution_output", None)
        if persist is not None:
            await persist(execution.id, result)
        return result

    NetworkExecutor._structured_output_base_execute = base_execute  # type: ignore[attr-defined]
    NetworkExecutor.execute = execute  # type: ignore[assignment]
