from fastapi import Depends

from modules.metering.application.providers import MeteringProviders
from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager


async def get_metering_providers(
    manager: SessionManager = Depends(get_session_manager),
) -> MeteringProviders:
    return MeteringProviders(manager.session)
