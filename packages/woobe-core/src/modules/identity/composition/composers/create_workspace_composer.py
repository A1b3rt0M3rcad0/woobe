from modules.identity.application.use_cases import CreateWorkspaceUseCase
from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import (
    SQLAlchemyOutboxEventWriter,
    SQLAlchemyWorkspaceRepository,
)
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.presentation.controllers.create_workspace_controller import (
    CreateWorkspaceController,
)
from shared.infra.transactional_handler import TransactionalHandler


def create_workspace_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    workspace_repo = SQLAlchemyWorkspaceRepository(uow)
    outbox = SQLAlchemyOutboxEventWriter(uow)
    use_case = CreateWorkspaceUseCase(workspace_repo, outbox)
    controller = CreateWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
