from modules.core.application.use_cases.project_access_use_cases import (
    GrantProjectAccessUseCase,
    GrantProjectSubjectAccessUseCase,
    ListAccessibleProjectsUseCase,
    ListProjectMembersUseCase,
    ListProjectsForAccessManagementUseCase,
    RevokeProjectAccessUseCase,
    RevokeProjectSubjectAccessUseCase,
)
from modules.core.composition.resources import DATABASE_ENGINE
from modules.core.infra.database.project_access_repository import (
    SQLAlchemyProjectAccessRepository,
)
from modules.core.infra.database.unit_of_work import CoreUnitOfWork
from modules.core.presentation.controllers.project_access_controller import (
    GrantProjectAccessController,
    GrantProjectSubjectAccessController,
    ListAccessibleProjectsController,
    ListProjectMembersController,
    ListProjectsForAccessManagementController,
    RevokeProjectAccessController,
    RevokeProjectSubjectAccessController,
)
from shared.infra.transactional_handler import TransactionalHandler


def list_accessible_projects_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ListAccessibleProjectsUseCase(repository)
    controller = ListAccessibleProjectsController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_projects_for_access_management_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ListProjectsForAccessManagementUseCase(repository)
    controller = ListProjectsForAccessManagementController(use_case)
    return TransactionalHandler(uow, controller.handle)


def list_project_members_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = ListProjectMembersUseCase(repository)
    controller = ListProjectMembersController(use_case)
    return TransactionalHandler(uow, controller.handle)


def grant_project_subject_access_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = GrantProjectSubjectAccessUseCase(repository)
    controller = GrantProjectSubjectAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def revoke_project_subject_access_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = RevokeProjectSubjectAccessUseCase(repository)
    controller = RevokeProjectSubjectAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def grant_project_access_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = GrantProjectAccessUseCase(repository)
    controller = GrantProjectAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)


def revoke_project_access_composer() -> TransactionalHandler:
    uow = CoreUnitOfWork(DATABASE_ENGINE)
    repository = SQLAlchemyProjectAccessRepository(uow)
    use_case = RevokeProjectAccessUseCase(repository)
    controller = RevokeProjectAccessController(use_case)
    return TransactionalHandler(uow, controller.handle)
