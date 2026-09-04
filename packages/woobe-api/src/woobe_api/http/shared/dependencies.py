from collections.abc import AsyncIterator

from fastapi import Request

from shared.infra.database.session_manager import SessionManager


async def get_session_manager(request: Request) -> AsyncIterator[SessionManager]:
    engine = request.app.state.async_engine
    async with SessionManager(engine) as manager:
        yield manager

