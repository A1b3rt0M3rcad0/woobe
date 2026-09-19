from __future__ import annotations

from modules.agent.infra.storage.factory import create_file_storage
from shared.composition_resources import (
    DATABASE_ENGINE,
    EXECUTION_STATE_STORE,
    RUN_EVENT_JOURNAL,
    SESSION_FACTORY,
    SETTINGS,
)
from shared.project_environment import ProjectEnvironmentService


FILE_STORAGE = create_file_storage(SETTINGS)


PROJECT_ENVIRONMENT = ProjectEnvironmentService(
    SESSION_FACTORY,
    encryption_key=SETTINGS.encryption_key,
)
