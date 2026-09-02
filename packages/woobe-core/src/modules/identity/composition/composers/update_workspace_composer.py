from modules.identity.application.use_cases import UpdateWorkspaceAsAdminUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.infra.database.workspace_access_repository import (
    SQLAlchemyWorkspaceAccessRepository,
)
from modules.identity.presentation.controllers.update_workspace_controller import (
    UpdateWorkspaceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def update_workspace_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    access_repo = SQLAlchemyWorkspaceAccessRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = UpdateWorkspaceAsAdminUseCase(workspace_repo, access_repo, outbox)
    controller = UpdateWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
