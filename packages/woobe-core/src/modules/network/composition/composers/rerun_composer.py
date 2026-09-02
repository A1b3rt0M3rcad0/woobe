from modules.network.application.use_cases.rerun_execution import (
    RerunNetworkExecutionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE
from modules.network.infra.database.rerun_repository import (
    SQLAlchemyNetworkRerunRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.presentation.controllers.rerun_controller import (
    RerunNetworkExecutionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def rerun_network_execution_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkRerunRepository(uow)
    use_case = RerunNetworkExecutionUseCase(repository)
    controller = RerunNetworkExecutionController(use_case)
    return TransactionalHandler(uow, controller.handle)
