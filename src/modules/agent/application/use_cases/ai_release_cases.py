from modules.agent.application.use_cases.release_lifecycle_use_cases import AutoCreateReleaseUseCase as CreateReleaseUseCase
from modules.agent.application.use_cases.release_lifecycle_use_cases import ReleaseLifecycleUseCase as PromoteReleaseUseCase


class RollbackReleaseUseCase(PromoteReleaseUseCase):
    pass
