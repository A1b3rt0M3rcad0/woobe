from typing import Any, Protocol
from uuid import UUID


class NetworkRunDiagnosticsReader(Protocol):
    async def get(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None: ...
