from modules.core.application.use_cases.get_chat_surface_credential import (
    GetChatSurfaceCredentialUseCase,
)
from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.chat_surface_credential_repository import (
    SQLAlchemyChatSurfaceCredentialRepository,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.get_chat_surface_credential_controller import (
    GetChatSurfaceCredentialController,
)
from shared.infra.transactional_handler import TransactionalHandler


def get_chat_surface_credential_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE).mark_read_only()
    repository = SQLAlchemyChatSurfaceCredentialRepository(uow)
    use_case = GetChatSurfaceCredentialUseCase(repository)
    controller = GetChatSurfaceCredentialController(use_case)
    return TransactionalHandler(uow, controller.handle)


__all__ = ["get_chat_surface_credential_composer"]
