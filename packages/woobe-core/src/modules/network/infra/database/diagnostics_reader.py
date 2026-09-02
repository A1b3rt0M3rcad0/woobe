from typing import Any
from uuid import UUID

from modules.network.application.interfaces.diagnostics_reader import (
    NetworkRunDiagnosticsReader,
)
from modules.network.infra.database.run_diagnostics_reader import (
    NetworkRunDiagnosticsReader as LegacyNetworkRunDiagnosticsReader,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork


class SQLAlchemyNetworkRunDiagnosticsReader(NetworkRunDiagnosticsReader):
    def __init__(self, uow: NetworkUnitOfWork) -> None:
        self._uow = uow

    async def get(
        self,
        execution_id: UUID,
        project_id: UUID,
    ) -> dict[str, Any] | None:
        return await LegacyNetworkRunDiagnosticsReader(self._uow.session).get(
            execution_id,
            project_id,
        )
