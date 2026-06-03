from uuid import UUID

from fastapi import Depends, Header, HTTPException

from modules.identity.domain.enums import UserSessionStatus
from modules.identity.infra.repositories import SQLAlchemyUserSessionRepository
from shared.presentation.dependencies import get_session_manager


async def get_current_user_id(
    authorization: str = Header(None),
    manager=Depends(get_session_manager),
) -> UUID:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")

    session_repo = SQLAlchemyUserSessionRepository(manager.session)

    sessions = await session_repo.list_by_user(
        UUID(int=0)
    )

    raise HTTPException(status_code=401, detail="Invalid session")
