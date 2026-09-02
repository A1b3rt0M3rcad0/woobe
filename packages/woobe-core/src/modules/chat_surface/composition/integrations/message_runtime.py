from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from modules.agent.entrypoint import build_agent_chat_surface_runtime
from modules.chat_surface.application.dtos.message_request import (
    BeginMessageRequestInput,
    BeginMessageRequestResult,
    CanonicalRunState,
    MarkMessageRequestInput,
    MessageBindingRuntimeContext,
    MessageRequestRuntimeContext,
    MessageRequestState,
)
from modules.chat_surface.application.use_cases.message_lifecycle import (
    BeginChatSurfaceMessageUseCase,
    MarkChatSurfaceMessageUseCase,
)
from modules.chat_surface.application.use_cases.message_transition import (
    resolve_message_transition,
    terminal_statuses,
)
from modules.chat_surface.composition.resources import DATABASE_ENGINE, SETTINGS
from modules.chat_surface.infra.database.message_request_repository import (
    SQLAlchemyChatSurfaceMessageRequestRepository,
)
from modules.chat_surface.infra.database.unit_of_work import ChatSurfaceUnitOfWork
from modules.network.entrypoint import build_network_chat_surface_runtime
from shared.contracts.errors import ConflictError, NotFoundError


_MESSAGE_ACTIVE = {"accepted", "streaming"}
_AGENT_ACTIVE = {"running", "cancel_requested"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}
_RUN_ACCEPTANCE_GRACE = timedelta(seconds=5)


class ChatSurfaceMessageRuntime:
    """Runtime-safe MessageRequest lifecycle using only short SQL scopes."""

    async def _context(
        self,
        request_id,
    ) -> MessageRequestRuntimeContext | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.get_runtime_context(request_id)

    async def _binding_context(
        self,
        *,
        surface_id,
        session_binding_id,
    ) -> MessageBindingRuntimeContext | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.get_binding_runtime_context(
                surface_id=surface_id,
                session_binding_id=session_binding_id,
            )

    async def _active_contexts(
        self,
        surface_id,
    ) -> list[MessageRequestRuntimeContext]:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.list_active_runtime_contexts(surface_id)

    async def _latest(
        self,
        session_binding_id,
    ) -> MessageRequestState | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.latest_for_binding(session_binding_id)

    async def _find_idempotent(
        self,
        *,
        session_binding_id,
        idempotency_key: str,
    ) -> MessageRequestState | None:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE).mark_read_only() as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            return await repository.find_idempotent(
                session_binding_id=session_binding_id,
                idempotency_key=idempotency_key,
            )

    async def _find_active_run(
        self,
        binding: MessageBindingRuntimeContext,
    ) -> CanonicalRunState | None:
        if binding.target_type == "agent":
            run = await build_agent_chat_surface_runtime().find_active(
                project_id=binding.project_id,
                agent_id=binding.target_id,
                session_id=binding.session_id,
                agent_release_id=binding.target_release_id,
            )
        else:
            run = await build_network_chat_surface_runtime().find_active(
                project_id=binding.project_id,
                network_id=binding.target_id,
                network_session_id=binding.session_id,
                network_version_id=binding.target_release_id,
            )
        return (
            CanonicalRunState(id=run.id, status=run.status)
            if run is not None
            else None
        )

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

    async def _persist_begin(
        self,
        input_dto: BeginMessageRequestInput,
    ) -> BeginMessageRequestResult:
        async with ChatSurfaceUnitOfWork(DATABASE_ENGINE) as uow:
            repository = SQLAlchemyChatSurfaceMessageRequestRepository(uow)
            use_case = BeginChatSurfaceMessageUseCase(
                repository,
                max_metadata_bytes=SETTINGS.runtime_max_metadata_bytes,
            )
            return await use_case.execute(input_dto)

    @staticmethod
    def _conflict(
        message: str,
        *,
        code: str,
        target_type: str,
        run: CanonicalRunState | None = None,
    ) -> ConflictError:
        error = ConflictError(message)
        error.code = code
        error.target_type = target_type
        if run is not None:
            error.run_id = run.id
            error.status = run.status
        return error

    @staticmethod
    def _is_active_run(target_type: str, status: str) -> bool:
        active = _AGENT_ACTIVE if target_type == "agent" else _NETWORK_ACTIVE
        return status in active

    @staticmethod
    def _observed_at(context: MessageRequestRuntimeContext) -> datetime | None:
        value = context.request.updated_at or context.request.created_at
        if value is not None and value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value

    async def _reconcile_context(
        self,
        context: MessageRequestRuntimeContext,
        *,
        now: datetime,
    ) -> CanonicalRunState | None:
        canonical = await self._resolve(
            context,
            context.request.target_run_id,
            wait_for_terminal=False,
        )
        if canonical is not None:
            if canonical.status in terminal_statuses(context.target_type):
                status = (
                    "completed"
                    if canonical.status == "completed"
                    else "cancelled"
                    if canonical.status == "cancelled"
                    else "failed"
                )
                await self.mark(
                    context.request.id,
                    status=status,
                    target_run_id=canonical.id,
                    error_code=(
                        None
                        if status in {"completed", "cancelled"}
                        else "runtime_failed"
                    ),
                )
            elif self._is_active_run(context.target_type, canonical.status):
                if (
                    context.request.status != "streaming"
                    or context.request.target_run_id != canonical.id
                ):
                    await self._persist(
                        MarkMessageRequestInput(
                            request_id=context.request.id,
                            status="streaming",
                            target_run_id=canonical.id,
                            error_code=None,
                        )
                    )
            return canonical

        observed_at = self._observed_at(context)
        if observed_at is not None and now - observed_at >= _RUN_ACCEPTANCE_GRACE:
            await self._persist(
                MarkMessageRequestInput(
                    request_id=context.request.id,
                    status="failed",
                    target_run_id=context.request.target_run_id,
                    error_code="run_acceptance_missing",
                )
            )
        return None

    async def _reconcile_surface(self, surface_id) -> None:
        now = datetime.now(UTC)
        contexts = await self._active_contexts(surface_id)
        for context in contexts:
            await self._reconcile_context(context, now=now)

    async def begin(
        self,
        *,
        surface_id,
        session_binding_id,
        idempotency_key: str,
        metadata: dict | None = None,
    ) -> BeginMessageRequestResult:
        normalized_key = idempotency_key.strip()
        existing = await self._find_idempotent(
            session_binding_id=session_binding_id,
            idempotency_key=normalized_key,
        )
        if existing is not None:
            return BeginMessageRequestResult(request=existing, created=False)

        await self._reconcile_surface(surface_id)

        binding = await self._binding_context(
            surface_id=surface_id,
            session_binding_id=session_binding_id,
        )
        if binding is None:
            raise NotFoundError("ChatSurface Session not found")

        active_run = await self._find_active_run(binding)
        if active_run is not None and self._is_active_run(
            binding.target_type,
            active_run.status,
        ):
            raise self._conflict(
                "ChatSurface Session already has an active Run",
                code="active_run_conflict",
                target_type=binding.target_type,
                run=active_run,
            )

        latest = await self._latest(session_binding_id)
        if latest is not None and latest.status in _MESSAGE_ACTIVE:
            context = await self._context(latest.id)
            canonical = (
                await self._reconcile_context(context, now=datetime.now(UTC))
                if context is not None
                else None
            )
            if canonical is not None and self._is_active_run(
                binding.target_type,
                canonical.status,
            ):
                raise self._conflict(
                    "ChatSurface Session already has an active Run",
                    code="active_run_conflict",
                    target_type=binding.target_type,
                    run=canonical,
                )
            remaining = await self._latest(session_binding_id)
            if remaining is not None and remaining.status in _MESSAGE_ACTIVE:
                raise self._conflict(
                    "ChatSurface Session already has an active message request",
                    code="active_message_request_conflict",
                    target_type=binding.target_type,
                )

        input_dto = BeginMessageRequestInput(
            surface_id=surface_id,
            session_binding_id=session_binding_id,
            idempotency_key=normalized_key,
            metadata=metadata,
        )
        try:
            return await self._persist_begin(input_dto)
        except ConflictError as exc:
            existing = await self._find_idempotent(
                session_binding_id=session_binding_id,
                idempotency_key=normalized_key,
            )
            if existing is not None:
                return BeginMessageRequestResult(request=existing, created=False)

            await self._reconcile_surface(surface_id)
            active_run = await self._find_active_run(binding)
            if active_run is not None and self._is_active_run(
                binding.target_type,
                active_run.status,
            ):
                raise self._conflict(
                    "ChatSurface Session already has an active Run",
                    code="active_run_conflict",
                    target_type=binding.target_type,
                    run=active_run,
                ) from exc

            latest = await self._latest(session_binding_id)
            if latest is not None and latest.status in _MESSAGE_ACTIVE:
                raise self._conflict(
                    "ChatSurface Session already has an active message request",
                    code="active_message_request_conflict",
                    target_type=binding.target_type,
                ) from exc

            try:
                return await self._persist_begin(input_dto)
            except ConflictError as retry_exc:
                raise self._conflict(
                    "ChatSurface Session already has an active message request",
                    code="active_message_request_conflict",
                    target_type=binding.target_type,
                ) from retry_exc

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
