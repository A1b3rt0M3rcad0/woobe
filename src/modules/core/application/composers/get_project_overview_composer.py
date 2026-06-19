from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.core.application.use_cases.get_project_overview import (
    GetProjectOverviewUseCase,
)
from modules.core.infra.database.project_overview_reader import (
    SQLAlchemyProjectOverviewReader,
)
from modules.core.presentation.controllers.get_project_overview_controller import (
    GetProjectOverviewController,
)
from shared.presentation.http.request import Request
from shared.presentation.http.response import Response

OverviewHandler = Callable[[Request], Awaitable[Response]]


def get_project_overview_composer(
    session_factory: async_sessionmaker[AsyncSession],
) -> OverviewHandler:
    reader = SQLAlchemyProjectOverviewReader(session_factory)
    use_case = GetProjectOverviewUseCase(reader)
    controller = GetProjectOverviewController(use_case)
    return controller.handle
