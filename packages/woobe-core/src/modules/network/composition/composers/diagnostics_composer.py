from modules.network.application.use_cases.diagnostics_use_cases import (
    GetNetworkRunDiagnosticsUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.diagnostics_reader import (
    SQLAlchemyNetworkRunDiagnosticsReader,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.diagnostics_controller import (
    GetNetworkRunDiagnosticsController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_network_run_diagnostics_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    reader = SQLAlchemyNetworkRunDiagnosticsReader(uow)
    use_case = GetNetworkRunDiagnosticsUseCase(reader)
    controller = GetNetworkRunDiagnosticsController(use_case)
    return TransactionalHandler(uow, controller.handle)
