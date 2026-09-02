from modules.network.application.use_cases.execution_control_use_cases import (
    CancelNetworkExecutionUseCase,
)
from modules.network.composition.resources import DATABASE_ENGINE, EXECUTION_STATE_STORE
from modules.network.infra.database.execution_control_repository import (
    SQLAlchemyNetworkExecutionControlRepository,
)
from modules.network.infra.database.unit_of_work import NetworkUnitOfWork
from modules.network.infra.runtime.redis_store import RedisNetworkExecutionStore
from modules.network.presentation.controllers.execution_control_controllers import (
    CancelNetworkExecutionController,
)
from shared.infra.transactional_handler import TransactionalHandler


def cancel_network_execution_composer() -> TransactionalHandler:
    uow = NetworkUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyNetworkExecutionControlRepository(uow)
    runtime_control = RedisNetworkExecutionStore(EXECUTION_STATE_STORE)
    use_case = CancelNetworkExecutionUseCase(repository, runtime_control)
    controller = CancelNetworkExecutionController(use_case)
    return TransactionalHandler(uow, controller.handle)
