from typing import Any

from modules.network.application.dtos.diagnostics import GetNetworkRunDiagnosticsInput
from modules.network.application.interfaces.diagnostics_reader import (
    NetworkRunDiagnosticsReader,
)
from shared.contracts.errors import NotFoundError


class GetNetworkRunDiagnosticsUseCase:
    def __init__(self, reader: NetworkRunDiagnosticsReader) -> None:
        self._reader = reader

    async def execute(
        self,
        input_dto: GetNetworkRunDiagnosticsInput,
    ) -> dict[str, Any]:
        diagnostics = await self._reader.get(
            input_dto.execution_id,
            input_dto.project_id,
        )
        if diagnostics is None:
            raise NotFoundError("Network execution not found")
        return diagnostics
