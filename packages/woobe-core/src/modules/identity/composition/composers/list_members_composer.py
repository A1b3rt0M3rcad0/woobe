from modules.identity.application.use_cases import ListMembersUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceMemberRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.list_members_controller import ListMembersController
from shared.infra.transactional_handler import TransactionalHandler


def list_members_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    member_repo = SQLAlchemyWorkspaceMemberRepository(uow)
    use_case = ListMembersUseCase(member_repo)
    controller = ListMembersController(use_case)
    return TransactionalHandler(uow, controller.handle)
