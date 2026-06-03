import hashlib
from uuid import UUID

from fastapi import Depends, Header, HTTPException

from modules.core.infra.repositories import SQLAlchemyApiKeyRepository
from shared.presentation.dependencies import get_session_manager


async def get_current_user_id(
    authorization: str = Header(None),
    manager=Depends(get_session_manager),
) -> UUID:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    raise HTTPException(status_code=401, detail="Invalid session")


async def get_project_context(
    authorization: str = Header(None),
    manager=Depends(get_session_manager),
) -> UUID:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing API key")

    key_hash = hashlib.sha256(authorization.encode()).digest()
    repo = SQLAlchemyApiKeyRepository(manager.session)
    api_key = await repo.get_by_key_hash(key_hash)
    if not api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")

    return api_key.project_id
