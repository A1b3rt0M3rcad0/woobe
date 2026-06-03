from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infra.database.session_manager import SessionManager
from shared.presentation.dependencies import get_session_manager


async def get_session(
    manager: SessionManager = Depends(get_session_manager),
) -> AsyncSession:
    return manager.session
