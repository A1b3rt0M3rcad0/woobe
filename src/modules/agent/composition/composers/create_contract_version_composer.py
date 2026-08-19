from modules.agent.application.use_cases import CreateContractUseCase
from modules.agent.infra.database.database import AgentDatabase
from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.create_contract_version_controller import CreateContractVersionController
from shared.infra.transactional_handler import TransactionalHandler


def create_contract_version_composer(database: AgentDatabase) -> TransactionalHandler:
    uow = AgentUnitOfWork(database)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = CreateContractUseCase(repo)
    controller = CreateContractVersionController(use_case)
    return TransactionalHandler(uow, controller.handle)
