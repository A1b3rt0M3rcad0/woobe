from __future__ import annotations

from modules.agent.infra.storage.factory import create_file_storage
from shared.composition_resources import (
    DATABASE_ENGINE,
    EXECUTION_STATE_STORE,
    RUN_EVENT_JOURNAL,
    SETTINGS,
)


FILE_STORAGE = create_file_storage(SETTINGS)
