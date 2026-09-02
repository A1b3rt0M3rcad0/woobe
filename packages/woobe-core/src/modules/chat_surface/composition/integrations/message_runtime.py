from __future__ import annotations

import asyncio

from modules.agent.entrypoint import build_agent_chat_surface_runtime
from modules.chat_surface.application.dtos.message_request import (
    CanonicalRunState,
    MarkMessageRequestInput,
    MessageRequestRuntimeContext,
    MessageRequestState,
)
from modules.chat_surface.application.use_cases.message_lifecycle import (
    MarkChatSurfaceMessageUseCase,
)
from modules.chat_surface.application.use_cases.message_transition import (
    resolve_message_transition,
    terminal_statuses,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE
from modules.chat_surface.infra.database.message_request_repository import (
    SQLAlchemyChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.network.entrypoint import build_network_chat_surface_runtime
from shared.contracts.errors import NotFoundError


_MESSAGE_ACTIVE = {"accepted", "streaming"}


class ChatSurfaceMessageRuntime:
    """Runtime-safe MessageRequest lifecycle using only short SQL scopes."""

    async def _context(
        self,
        request_id,
    ) -> MessageRequestRuntimeContext | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.get_runtime_context(request_id)

    async def _resolve_once(
        self,
        context: MessageRequestRuntimeContext,
        run_id,
    ) -> CanonicalRunState | None:
        if context.target_type == "agent":
            runtime = build_agent_chat_surface_runtime()
            try:
                run = (
                    await runtime.get(
                        run_id=run_id,
                        project_id=context.project_id,
                        agent_id=context.target_id,
                        session_id=context.session_id,
                        agent_release_id=context.target_release_id,
                    )
                    if run_id is not None
                    else await runtime.find_latest(
                        project_id=context.project_id,
                        agent_id=context.target_id,
                        session_id=context.session_id,
                        agent_release_id=context.target_release_id,
                        created_after=context.request.created_at,
                    )
                )
            except NotFoundError:
                return None
        else:
            runtime = build_network_chat_surface_runtime()
            try:
                run = (
                    await runtime.get(
                        run_id=run_id,
                        project_id=context.project_id,
                        network_id=context.target_id,
                        network_session_id=context.session_id,
                        network_version_id=context.target_release_id,
                    )
                    if run_id is not None
                    else await runtime.find_latest(
                        project_id=context.project_id,
                        network_id=context.target_id,
                        network_session_id=context.session_id,
                        network_version_id=context.target_release_id,
                        created_after=context.request.created_at,
                    )
                )
            except NotFoundError:
                return None
        if run is None:
            return None
        return CanonicalRunState(id=run.id, status=run.status)

    async def _resolve(
        self,
        context: MessageRequestRuntimeContext,
        run_id,
        *,
        wait_for_terminal: bool,
    ) -> CanonicalRunState | None:
        attempts = 20 if wait_for_terminal else 1
        latest: CanonicalRunState | None = None
        terminal = terminal_statuses(context.target_type)
        for attempt in range(attempts):
            latest = await self._resolve_once(context, run_id)
            if not wait_for_terminal or (
                latest is not None and latest.status in terminal
            ):
                return latest
            if attempt + 1 < attempts:
                await asyncio.sleep(0.05)
        return latest

    async def _persist(
        self,
        input_dto: MarkMessageRequestInput,
    ) -> MessageRequestState | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE) as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await MarkChatSurfaceMessageUseCase(repository).execute(input_dto)

    async def mark(
        self,
        request_id,
        *,
        status: str,
        target_run_id=None,
        error_code: str | None = None,
    ) -> MessageRequestState | None:
        context = await self._context(request_id)
        if context is None:
            return None
        requested = MarkMessageRequestInput(
            request_id=request_id,
            status=status,
            target_run_id=target_run_id,
            error_code=error_code,
        )
        wait_for_terminal = (
            status in {"completed", "failed", "cancelled"}
            and context.request.status in _MESSAGE_ACTIVE
        )
        canonical = await self._resolve(
            context,
            target_run_id or context.request.target_run_id,
            wait_for_terminal=wait_for_terminal,
        )
        decision = resolve_message_transition(
            target_type=context.target_type,
            current=context.request,
            requested=requested,
            canonical_run=canonical,
        )
        return await self._persist(
            MarkMessageRequestInput(
                request_id=request_id,
                status=decision.status,
                target_run_id=decision.target_run_id,
                error_code=decision.error_code,
            )
        )


__all__ = ["ChatSurfaceMessageRuntime"]
