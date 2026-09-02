from modules.identity.application.use_cases import ListWorkspacesUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.list_workspaces_controller import (
    ListWorkspacesController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_workspaces_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    use_case = ListWorkspacesUseCase(workspace_repo)
    controller = ListWorkspacesController(use_case)
    return TransactionalHandler(uow, controller.handle)
