from __future__ import annotations

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

    async def _resolve_request_run(
        self,
        request: ChatSurfaceMessageRequestModel,
        binding: ChatSurfaceSessionBindingModel,
    ) -> tuple[UUID | None, str | None]:
        async with self._session_factory() as session:
            if binding.target_type == "agent":
                run = (
                    await session.get(AgentRunModel, request.target_run_id)
                    if request.target_run_id is not None
                    else await session.scalar(
                        select(AgentRunModel)
                        .where(
                            AgentRunModel.session_id == binding.session_id,
                            AgentRunModel.agent_id == binding.target_id,
                            AgentRunModel.project_id == binding.project_id,
                            AgentRunModel.agent_release_id == binding.target_release_id,
                            AgentRunModel.network_execution_id.is_(None),
                            AgentRunModel.status == "running",
                        )
                        .order_by(
                            AgentRunModel.created_at.desc(),
                            AgentRunModel.id.desc(),
                        )
                        .limit(1)
                    )
                )
                if run is None:
                    return request.target_run_id, None
                return run.id, str(run.status)

            execution = (
                await session.get(NetworkExecutionModel, request.target_run_id)
                if request.target_run_id is not None
                else await session.scalar(
                    select(NetworkExecutionModel)
                    .where(
                        NetworkExecutionModel.network_session_id == binding.session_id,
                        NetworkExecutionModel.network_id == binding.target_id,
                        NetworkExecutionModel.project_id == binding.project_id,
                        NetworkExecutionModel.network_version_id
                        == binding.target_release_id,
                        NetworkExecutionModel.status.in_(
                            {"queued", "running", "cancel_requested"}
                        ),
                    )
                    .order_by(
                        NetworkExecutionModel.created_at.desc(),
                        NetworkExecutionModel.id.desc(),
                    )
                    .limit(1)
                )
            )
            if execution is None:
                return request.target_run_id, None
            return execution.id, str(execution.status)

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
                    ChatSurfaceMessageRequestModel.status.in_(
                        {"accepted", "streaming"}
                    ),
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
                error_code=None if status == "completed" else "runtime_failed",
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
        """Do not turn an observer disconnect into a terminal message request.

        Existing ChatSurface stream generators historically marked the request when
        the HTTP iterator ended. With detached Runs, an iterator can end because the
        observer disappeared while the Run is still executing. Resolve the canonical
        Run first and keep the message request `streaming` until durable execution is
        actually terminal.
        """
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

        if target_run_id is not None:
            request.target_run_id = target_run_id
        run_id, run_status = await self._resolve_request_run(request, binding)

        if status in {"completed", "failed", "cancelled"} and run_status is not None:
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
            error_code = None if status == "completed" else error_code or "runtime_failed"

        await super().mark_message(
            request_id,
            status=status,
            target_run_id=run_id or target_run_id,
            error_code=error_code,
        )


__all__ = ["CONTROL_PLANE_TEST_SOURCE", "ControlPlaneChatSurfaceService"]
