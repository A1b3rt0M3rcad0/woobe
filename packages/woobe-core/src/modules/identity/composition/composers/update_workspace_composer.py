from modules.identity.composition.resources import DATABASE_ENGINE
from modules.identity.infra.database.repositories import SQLAlchemyOutboxEventWriter
from modules.identity.infra.database.repositories import SQLAlchemyWorkspaceRepository
from modules.identity.infra.database.unit_of_work import IdentityUnitOfWork
from modules.identity.application.use_cases import UpdateWorkspaceUseCase
from modules.identity.presentation.controllers.update_workspace_controller import UpdateWorkspaceController
from shared.infra.transactional_handler import TransactionalHandler


def update_workspace_composer() -> TransactionalHandler:
    uow = IdentityUnitOfWork(DATABASE_ENGINE)
    use_case = UpdateWorkspaceUseCase(SQLAlchemyWorkspaceRepository(uow), SQLAlchemyOutboxEventWriter(uow))
    controller = UpdateWorkspaceController(use_case)
    return TransactionalHandler(uow, controller.handle)
