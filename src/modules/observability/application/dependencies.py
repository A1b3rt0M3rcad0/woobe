from fastapi import Depends

from modules.observability.application.providers import ObservabilityProviders
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager


async def get_observability_providers(
    manager: SessionManager = Depends(get_session_manager),
) -> ObservabilityProviders:
    return ObservabilityProviders(manager.session)
