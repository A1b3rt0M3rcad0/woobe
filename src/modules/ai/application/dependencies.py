from uuid import UUID

from fastapi import Depends, Header, HTTPException

from modules.ai.infra.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from shared.presentation.dependencies import get_session_manager


async def verify_project_access(
    x_project_id: str = Header(None),
    manager=Depends(get_session_manager),
) -> UUID:
    if not x_project_id:
        raise HTTPException(status_code=400, detail="Missing X-Project-Id header")
    try:
        return UUID(x_project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project ID")
