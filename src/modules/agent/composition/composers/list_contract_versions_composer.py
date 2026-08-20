from modules.agent.application.use_cases import ListContractsUseCase
from modules.agent.composition.resources import DATABASE_ENGINE
from modules.agent.infra.database.repositories import SQLAlchemyAgentContractRepository
from modules.agent.infra.database.unit_of_work import AgentUnitOfWork
from modules.agent.presentation.controllers.list_contract_versions_controller import ListContractVersionsController
from shared.infra.transactional_handler import TransactionalHandler


def list_contract_versions_composer() -> TransactionalHandler:
    uow = AgentUnitOfWork(DATABASE_ENGINE)
    repo = SQLAlchemyAgentContractRepository(uow)
    use_case = ListContractsUseCase(repo)
    controller = ListContractVersionsController(use_case)
    return TransactionalHandler(uow, controller.handle)
