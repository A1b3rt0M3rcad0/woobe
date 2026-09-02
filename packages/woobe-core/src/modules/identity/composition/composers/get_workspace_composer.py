from modules.identity.application.use_cases import GetWorkspaceForMemberUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.database.workspace_access_repository import (
    SQLAlchemyWorkspaceAccessRepository,
)
from modules.identity.presentation.controllers.get_workspace_controller import (
    GetWorkspaceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_workspace_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    use_case = GetWorkspaceForMemberUseCase(workspace_repo, access_repo)
    controller = GetWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
