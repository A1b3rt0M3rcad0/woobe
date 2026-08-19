from modules.agent.application.use_cases import UpdateContractUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.update_contract_version_controller import UpdateContractVersionController
from shared.infra.transactional_handler import TransactionalHandler


def update_contract_version_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = UpdateContractUseCase(repo)
    controller = UpdateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
