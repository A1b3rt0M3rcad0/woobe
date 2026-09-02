from typing import Any, Protocol
from uuid import UUID


class AgentRuntimeBindingGateway(Protocol):
    async def resolve_runtime_bindings(
        self,
        *,
        project_id: UUID,
        nodes: list[dict[str, Any]],
    ) -> dict[str, dict[str, Any]]: ...
