from __future__ import annotations

from typing import Any

from modules.agent.infra.execution.instrumented_execution_finalizer import (
    finalize_instrumented_execution,
)
from modules.agent.infra.execution.instrumented_failed_finalizer import (
    finalize_failed_instrumented_execution,
)
from shared.runtime.event_schema import LEGACY_STORAGE_VERSION


class LegacyAgentRunPersistence:
    storage_version = LEGACY_STORAGE_VERSION

    async def complete(self, owner: Any, **kwargs: Any):
        return await finalize_instrumented_execution(owner, **kwargs)

    async def fail(self, owner: Any, **kwargs: Any) -> None:
        await finalize_failed_instrumented_execution(owner, **kwargs)

    async def prepare_failure(
        self,
        owner: Any,
        *,
        input_dto: Any,
        error: Exception,
    ) -> bool:
        await owner._persist_prepare_failure_legacy(input_dto, error)
        return True
