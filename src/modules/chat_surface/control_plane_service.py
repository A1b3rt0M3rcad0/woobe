from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

from sqlalchemy import select

from modules.agent.infra.database.models import SessionModel
from modules.agent.infra.database.run_models import AgentRunModel
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.presentation.schemas import CreateSurfaceSessionRequest
from modules.chat_surface.security import normalize_origin
from modules.chat_surface.service import (
    AuthorizedChatSession,
    ChatSurfaceService,
    SurfaceCredential,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkSessionModel,
)
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
)
from shared.runtime_environment import assert_runtime_environment_enabled


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"
_AGENT_TERMINAL = {"completed", "failed", "cancelled", "uncertain"}
_NETWORK_TERMINAL = {"completed", "failed", "cancelled", "timed_out", "uncertain"}
_AGENT_ACTIVE = {"running"}
_NETWORK_ACTIVE = {"queued", "running", "cancel_requested"}
_MESSAGE_ACTIVE = {"accepted", "streaming"}


class ControlPlaneChatSurfaceService(ChatSurfaceService):
    """Adds authenticated Control Plane testing and truthful Run observation."""

    async def create_test_session(
        self,
        *,
        surface_id: UUID,
        actor_id: UUID,
        origin: str,
    ):
        surface = await self.get_surface(surface_id)
        if surface.status != "active":
            raise ConflictError("ChatSurface must be active before it can be tested")

        normalized_origin = normalize_origin(
            origin,
            allow_insecure=self._allow_insecure_origins,
        )
        synthetic_credential = SurfaceCredential(
            api_key_id=uuid4(),
            project_id=surface.project_id,
            chat_surface_id=surface.id,
            scopes=frozenset({"surface:sessions:create"}),
        )
        binding = await self.create_session(
            surface=surface,
            credential=synthetic_credential,
            idempotency_key=f"control-plane-test:{uuid4()}",
            payload=CreateSurfaceSessionRequest(
                metadata={
                    "source": CONTROL_PLANE_TEST_SOURCE,
                    "actor_id": str(actor_id),
                }
            ),
        )

        refreshed_surface = await self.get_surface(surface.id)
        if refreshed_surface.status != "active":
            raise ConflictError("ChatSurface became inactive while creating the test Session")

        token = self._token_codec.issue(
            project_id=refreshed_surface.project_id,
            chat_surface_id=refreshed_surface.id,
            target_type=refreshed_surface.target_type,
            target_id=refreshed_surface.target_id,
            target_release_id=binding.target_release_id,
            session_id=binding.session_id,
            origin=normalized_origin,
            surface_credential_id=binding.surface_credential_id,
            token_epoch=refreshed_surface.token_epoch,
            ttl_seconds=refreshed_surface.session_token_ttl_seconds,
        )
        return token, binding, refreshed_surface

    async def authorize_session_token(
        self,
        token: str,
        *,
        expected_session_id: UUID,
        host_origin: str | None,
        permission: str,
    ) -> AuthorizedChatSession:
        claims = self._token_codec.decode(token)
        if claims.session_id != expected_session_id:
            raise NotFoundError("ChatSurface Session not found")
        if permission not in claims.permissions:
            raise AuthorizationError("ChatSurface Session token scope is insufficient")

        binding = await self.get_binding(
            surface_id=claims.chat_surface_id,
            session_id=claims.session_id,
        )
        metadata = dict(binding.metadata_ or {})
        if metadata.get("source") != CONTROL_PLANE_TEST_SOURCE:
            return await super().authorize_session_token(
                token,
                expected_session_id=expected_session_id,
                host_origin=host_origin,
                permission=permission,
            )

        if not host_origin:
            raise AuthorizationError("X-Woobe-Host-Origin is required")
        normalized_origin = normalize_origin(
            host_origin,
            allow_insecure=self._allow_insecure_origins,
        )
        if normalized_origin != claims.origin:
            raise AuthorizationError("ChatSurface Session origin does not match")
        if binding.surface_credential_id != claims.surface_credential_id:
            raise AuthenticationError("ChatSurface test Session token is inactive")

        async with self._session_factory() as session:
            # Public Sessions always point to a persisted Access Key. A Control Plane
            # test Session deliberately uses a synthetic UUID, so externally supplied
            # metadata cannot opt into the relaxed origin policy.
            credential = await session.get(ApiKeyModel, claims.surface_credential_id)
            if credential is not None:
                raise AuthenticationError("ChatSurface test Session token is inactive")

            surface = await session.get(ChatSurfaceModel, claims.chat_surface_id)
            if (
                surface is None
                or surface.status != "active"
                or surface.project_id != claims.project_id
                or surface.target_type != claims.target_type
                or surface.target_id != claims.target_id
                or surface.token_epoch != claims.token_epoch
                or binding.status != "active"
                or binding.project_id != claims.project_id
                or binding.target_type != claims.target_type
                or binding.target_id != claims.target_id
                or binding.target_release_id != claims.target_release_id
            ):
                raise AuthenticationError("ChatSurface test Session token is inactive")

            await assert_runtime_environment_enabled(
                session,
                target_type=surface.target_type,
                target_id=surface.target_id,
                project_id=surface.project_id,
                environment="production",
            )

            if binding.target_type == "agent":
                target_session = await session.get(SessionModel, binding.session_id)
                valid_target_session = (
                    target_session is not None
                    and target_session.project_id == binding.project_id
                    and target_session.agent_id == binding.target_id
                    and target_session.runtime_environment == "production"
                    and target_session.opened_release_id == binding.target_release_id
                    and target_session.chat_surface_id == surface.id
                    and target_session.origin == "chat_surface"
                    and target_session.status == "active"
                )
            else:
                target_session = await session.get(
                    NetworkSessionModel,
                    binding.session_id,
                )
                valid_target_session = (
                    target_session is not None
                    and target_session.project_id == binding.project_id
                    and target_session.network_id == binding.target_id
                    and target_session.environment == "production"
                    and target_session.network_version_id == binding.target_release_id
                    and target_session.chat_surface_id == surface.id
                    and target_session.origin == "chat_surface"
                    and target_session.status == "active"
                )
            if not valid_target_session:
                raise NotFoundError("ChatSurface Session not found")

            return AuthorizedChatSession(
                surface=surface,
                binding=binding,
                claims=claims,
            )

    async def _active_run_for_binding(
        self,
        binding: ChatSurfaceSessionBindingModel,
    ) -> tuple[UUID | None, str | None]:
        async with self._session_factory() as session:
            if binding.target_type == "agent":
                run = await session.scalar(
                    select(AgentRunModel)
                    .where(
                        AgentRunModel.session_id == binding.session_id,
                        AgentRunModel.agent_id == binding.target_id,
                        AgentRunModel.project_id == binding.project_id,
                        AgentRunModel.agent_release_id == binding.target_release_id,
                        AgentRunModel.network_execution_id.is_(None),
                        AgentRunModel.status.in_(_AGENT_ACTIVE),
                    )
                    .order_by(
                        AgentRunModel.created_at.desc(),
                        AgentRunModel.id.desc(),
                    )
                    .limit(1)
                )
                return (run.id, str(run.status)) if run is not None else (None, None)

            execution = await session.scalar(
                select(NetworkExecutionModel)
                .where(
                    NetworkExecutionModel.network_session_id == binding.session_id,
                    NetworkExecutionModel.network_id == binding.target_id,
                    NetworkExecutionModel.project_id == binding.project_id,
                    NetworkExecutionModel.network_version_id == binding.target_release_id,
                    NetworkExecutionModel.status.in_(_NETWORK_ACTIVE),
                )
                .order_by(
                    NetworkExecutionModel.created_at.desc(),
                    NetworkExecutionModel.id.desc(),
                )
                .limit(1)
            )
            return (
                (execution.id, str(execution.status))
                if execution is not None
                else (None, None)
            )

    async def _resolve_request_run(
        self,
        request: ChatSurfaceMessageRequestModel,
        binding: ChatSurfaceSessionBindingModel,
    ) -> tuple[UUID | None, str | None]:
        async with self._session_factory() as session:
            if binding.target_type == "agent":
                if request.target_run_id is not None:
                    run = await session.get(AgentRunModel, request.target_run_id)
                else:
                    run = await session.scalar(
                        select(AgentRunModel)
                        .where(
                            AgentRunModel.session_id == binding.session_id,
                            AgentRunModel.agent_id == binding.target_id,
                            AgentRunModel.project_id == binding.project_id,
                            AgentRunModel.agent_release_id == binding.target_release_id,
                            AgentRunModel.network_execution_id.is_(None),
                            AgentRunModel.created_at >= request.created_at,
                        )
                        .order_by(
                            AgentRunModel.created_at.desc(),
                            AgentRunModel.id.desc(),
                        )
                        .limit(1)
                    )
                if run is None:
                    return request.target_run_id, None
                if (
                    run.session_id != binding.session_id
                    or run.agent_id != binding.target_id
                    or run.project_id != binding.project_id
                    or run.agent_release_id != binding.target_release_id
                    or run.network_execution_id is not None
                ):
                    return None, None
                return run.id, str(run.status)

            if request.target_run_id is not None:
                execution = await session.get(
                    NetworkExecutionModel,
                    request.target_run_id,
                )
            else:
                execution = await session.scalar(
                    select(NetworkExecutionModel)
                    .where(
                        NetworkExecutionModel.network_session_id == binding.session_id,
                        NetworkExecutionModel.network_id == binding.target_id,
                        NetworkExecutionModel.project_id == binding.project_id,
                        NetworkExecutionModel.network_version_id
                        == binding.target_release_id,
                        NetworkExecutionModel.created_at >= request.created_at,
                    )
                    .order_by(
                        NetworkExecutionModel.created_at.desc(),
                        NetworkExecutionModel.id.desc(),
                    )
                    .limit(1)
                )
            if execution is None:
                return request.target_run_id, None
            if (
                execution.network_session_id != binding.session_id
                or execution.network_id != binding.target_id
                or execution.project_id != binding.project_id
                or execution.network_version_id != binding.target_release_id
            ):
                return None, None
            return execution.id, str(execution.status)

    async def begin_message(
        self,
        authorized: AuthorizedChatSession,
        idempotency_key: str,
        *,
        metadata: dict | None = None,
    ) -> tuple[ChatSurfaceMessageRequestModel, bool]:
        normalized_key = idempotency_key.strip()
        async with self._session_factory() as session:
            existing = await session.scalar(
                select(ChatSurfaceMessageRequestModel).where(
                    ChatSurfaceMessageRequestModel.session_binding_id
                    == authorized.binding.id,
                    ChatSurfaceMessageRequestModel.idempotency_key == normalized_key,
                )
            )
        if existing is not None:
            return await super().begin_message(
                authorized,
                idempotency_key,
                metadata=metadata,
            )

        run_id, run_status = await self._active_run_for_binding(authorized.binding)
        if run_id is not None and run_status in (_AGENT_ACTIVE | _NETWORK_ACTIVE):
            raise ConflictError("ChatSurface Session already has an active Run")

        return await super().begin_message(
            authorized,
            idempotency_key,
            metadata=metadata,
        )

    async def active_message_request(
        self,
        authorized: AuthorizedChatSession,
    ) -> ChatSurfaceMessageRequestModel | None:
        async with self._session_factory() as session:
            request = await session.scalar(
                select(ChatSurfaceMessageRequestModel)
                .where(
                    ChatSurfaceMessageRequestModel.session_binding_id
                    == authorized.binding.id,
                    ChatSurfaceMessageRequestModel.status.in_(_MESSAGE_ACTIVE),
                )
                .order_by(
                    ChatSurfaceMessageRequestModel.created_at.desc(),
                    ChatSurfaceMessageRequestModel.id.desc(),
                )
                .limit(1)
            )
        if request is None:
            return None

        run_id, run_status = await self._resolve_request_run(request, authorized.binding)
        if run_id is not None and request.target_run_id != run_id:
            await super().mark_message(
                request.id,
                status="streaming",
                target_run_id=run_id,
            )
            request.target_run_id = run_id
            request.status = "streaming"

        terminal_statuses = (
            _AGENT_TERMINAL
            if authorized.binding.target_type == "agent"
            else _NETWORK_TERMINAL
        )
        if run_status in terminal_statuses:
            status = (
                "completed"
                if run_status == "completed"
                else "cancelled"
                if run_status == "cancelled"
                else "failed"
            )
            await super().mark_message(
                request.id,
                status=status,
                target_run_id=run_id,
                error_code=(
                    None if status in {"completed", "cancelled"} else "runtime_failed"
                ),
            )
            return None
        return request

    async def mark_message(
        self,
        request_id: UUID,
        *,
        status: str,
        target_run_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None:
        """Keep message lifecycle tied to the Run, never to one SSE observer."""
        async with self._session_factory() as session:
            request = await session.get(ChatSurfaceMessageRequestModel, request_id)
            binding = (
                await session.get(
                    ChatSurfaceSessionBindingModel,
                    request.session_binding_id,
                )
                if request is not None
                else None
            )
        if request is None or binding is None:
            return

        original_status = str(request.status)
        if target_run_id is not None:
            request.target_run_id = target_run_id
        run_id, run_status = await self._resolve_request_run(request, binding)

        requested_terminal = status in {"completed", "failed", "cancelled"}
        if requested_terminal and run_status is None and original_status in _MESSAGE_ACTIVE:
            # Acceptance and ChatSurface bookkeeping use separate transactions. Give
            # the canonical Run a short grace period to become queryable before an
            # observer ending is allowed to release the active-message gate.
            for _ in range(20):
                await asyncio.sleep(0.05)
                run_id, run_status = await self._resolve_request_run(request, binding)
                if run_status is not None:
                    break

        if requested_terminal and run_status is not None:
            terminal_statuses = (
                _AGENT_TERMINAL if binding.target_type == "agent" else _NETWORK_TERMINAL
            )
            if run_status not in terminal_statuses:
                await super().mark_message(
                    request_id,
                    status="streaming",
                    target_run_id=run_id,
                    error_code=None,
                )
                return
            status = (
                "completed"
                if run_status == "completed"
                else "cancelled"
                if run_status == "cancelled"
                else "failed"
            )
            error_code = (
                None
                if status in {"completed", "cancelled"}
                else error_code or "runtime_failed"
            )

        # A successful observer iterator with no canonical Run is not proof that the
        # execution completed. Preserve the gate; reattach or stale-run recovery can
        # resolve it without allowing a duplicate message to start concurrently.
        if (
            status == "completed"
            and run_status is None
            and original_status in _MESSAGE_ACTIVE
        ):
            await super().mark_message(
                request_id,
                status="streaming",
                target_run_id=run_id or target_run_id,
                error_code=None,
            )
            return

        await super().mark_message(
            request_id,
            status=status,
            target_run_id=run_id or target_run_id,
            error_code=error_code,
        )


__all__ = ["CONTROL_PLANE_TEST_SOURCE", "ControlPlaneChatSurfaceService"]
