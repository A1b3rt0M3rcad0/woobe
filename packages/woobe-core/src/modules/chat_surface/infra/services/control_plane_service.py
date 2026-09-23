from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from modules.agent.infra.database.models import AgentReleaseModel, SessionModel
from modules.chat_surface.application.runtime_gateway import (
    ChatMessageRequestSnapshot,
    ChatRuntimeGateway,
    ChatRuntimeTarget,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.application.dtos import CreateSurfaceSessionRequest
from modules.chat_surface.application.security import normalize_origin
from modules.chat_surface.infra.services.chat_surface_service import (
    AuthorizedChatSession,
    ChatSurfaceService,
    SurfaceCredential,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.network.infra.database.models import NetworkSessionModel, NetworkVersionModel
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
_RUN_ACCEPTANCE_GRACE = timedelta(seconds=5)


class ControlPlaneChatSurfaceService(ChatSurfaceService):
    """Adds authenticated Control Plane testing and truthful Run observation."""

    def __init__(
        self,
        session_factory,
        token_codec,
        *,
        runtime_gateway: ChatRuntimeGateway | None = None,
        allow_insecure_origins: bool = False,
        max_metadata_bytes: int = 16_384,
    ) -> None:
        super().__init__(
            session_factory,
            token_codec,
            allow_insecure_origins=allow_insecure_origins,
            max_metadata_bytes=max_metadata_bytes,
        )
        self._runtime_gateway = runtime_gateway

    def _runtime(self) -> ChatRuntimeGateway:
        if self._runtime_gateway is None:
            raise RuntimeError("ChatSurface runtime gateway is not configured")
        return self._runtime_gateway

    @staticmethod
    def _runtime_target(
        binding: ChatSurfaceSessionBindingModel,
    ) -> ChatRuntimeTarget:
        return ChatRuntimeTarget(
            project_id=binding.project_id,
            target_type=binding.target_type,
            target_id=binding.target_id,
            target_release_id=binding.target_release_id,
            session_id=binding.session_id,
        )

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

    async def embed_configuration(self, authorized: AuthorizedChatSession) -> dict:
        configuration = super().embed_configuration(authorized)
        async with self._session_factory() as session:
            if authorized.binding.target_type == "agent":
                target_session = await session.get(SessionModel, authorized.binding.session_id)
                release = await session.get(
                    AgentReleaseModel,
                    authorized.binding.target_release_id,
                )
                contract = getattr(release, "external_context_contract", None) or {}
            else:
                target_session = await session.get(
                    NetworkSessionModel,
                    authorized.binding.session_id,
                )
                version = await session.get(
                    NetworkVersionModel,
                    authorized.binding.target_release_id,
                )
                contract = getattr(version, "effective_external_context_contract", None) or {}

        fields = (
            contract.get("fields", {})
            if isinstance(contract, dict) and isinstance(contract.get("fields"), dict)
            else contract
        )
        if not isinstance(fields, dict):
            fields = {}
        session_fields = sorted(
            str(name)
            for name, field in fields.items()
            if isinstance(field, dict) and field.get("scope", "run") == "session"
        )
        snapshot = getattr(target_session, "external_context_snapshot", None) or {}
        return {
            **configuration,
            "external_context_session_fields": session_fields,
            "external_context_locked_fields": sorted(str(name) for name in snapshot),
        }

    async def _active_run_for_binding(
        self,
        binding: ChatSurfaceSessionBindingModel,
    ) -> tuple[UUID | None, str | None]:
        identity = await self._runtime().resolve_run(
            self._runtime_target(binding),
        )
        if identity is None:
            return None, None
        return identity.run_id, identity.status

    async def _resolve_request_run(
        self,
        request: ChatSurfaceMessageRequestModel,
        binding: ChatSurfaceSessionBindingModel,
    ) -> tuple[UUID | None, str | None]:
        identity = await self._runtime().resolve_run(
            self._runtime_target(binding),
            preferred_run_id=request.target_run_id,
            created_after=(
                None if request.target_run_id is not None else request.created_at
            ),
        )
        if identity is None:
            return None, None
        return identity.run_id, identity.status

    async def _reconcile_surface_active_messages(self, surface_id: UUID) -> None:
        """Release stale ChatSurface admission leases across all Sessions."""
        async with self._session_factory() as session:
            result = await session.execute(
                select(
                    ChatSurfaceMessageRequestModel,
                    ChatSurfaceSessionBindingModel,
                )
                .join(
                    ChatSurfaceSessionBindingModel,
                    ChatSurfaceSessionBindingModel.id
                    == ChatSurfaceMessageRequestModel.session_binding_id,
                )
                .where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                    ChatSurfaceMessageRequestModel.status.in_(_MESSAGE_ACTIVE),
                )
                .order_by(
                    ChatSurfaceMessageRequestModel.created_at.asc(),
                    ChatSurfaceMessageRequestModel.id.asc(),
                )
            )
            candidates = list(result.all())

        now = datetime.now(timezone.utc)
        for request, binding in candidates:
            run_id, run_status = await self._resolve_request_run(request, binding)
            terminal_statuses = (
                _AGENT_TERMINAL
                if binding.target_type == "agent"
                else _NETWORK_TERMINAL
            )
            active_statuses = (
                _AGENT_ACTIVE if binding.target_type == "agent" else _NETWORK_ACTIVE
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
                        None
                        if status in {"completed", "cancelled"}
                        else "runtime_failed"
                    ),
                )
                continue

            if run_status in active_statuses:
                if run_id is not None and request.target_run_id != run_id:
                    await super().mark_message(
                        request.id,
                        status="streaming",
                        target_run_id=run_id,
                        error_code=None,
                    )
                continue

            if run_status is not None:
                continue

            observed_at = getattr(request, "updated_at", None) or getattr(
                request,
                "created_at",
                None,
            )
            if observed_at is None:
                continue
            if observed_at.tzinfo is None:
                observed_at = observed_at.replace(tzinfo=timezone.utc)
            if now - observed_at < _RUN_ACCEPTANCE_GRACE:
                continue

            await super().mark_message(
                request.id,
                status="failed",
                target_run_id=run_id or request.target_run_id,
                error_code="run_acceptance_missing",
            )

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

        # max_concurrent_runs is Surface-wide, so its admission leases must be
        # reconciled Surface-wide as well. Otherwise an orphan from an old Session
        # permanently consumes capacity and every new Session receives HTTP 429.
        await self._reconcile_surface_active_messages(authorized.surface.id)

        run_id, run_status = await self._active_run_for_binding(authorized.binding)
        if run_id is not None and run_status in (_AGENT_ACTIVE | _NETWORK_ACTIVE):
            error = ConflictError("ChatSurface Session already has an active Run")
            error.code = "active_run_conflict"
            error.run_id = run_id
            error.status = run_status
            error.target_type = authorized.binding.target_type
            raise error

        # MessageRequest is bookkeeping; the canonical Run owns lifecycle. Give a
        # just-accepted Run a bounded grace period to materialize, then release an
        # orphaned gate instead of poisoning the Session indefinitely.
        active_request = await self.active_message_request(authorized)
        if active_request is not None:
            error = ConflictError("ChatSurface Session already has an active message request")
            error.code = "active_message_request_conflict"
            error.target_type = authorized.binding.target_type
            raise error

        try:
            return await super().begin_message(
                authorized,
                idempotency_key,
                metadata=metadata,
            )
        except ConflictError as exc:
            if str(exc) != "ChatSurface Session already has an active Run":
                raise

            # The active-message partial index can race with terminal persistence.
            # Reconcile once from canonical Run state, then retry the insert once.
            run_id, run_status = await self._active_run_for_binding(authorized.binding)
            if run_id is not None and run_status in (_AGENT_ACTIVE | _NETWORK_ACTIVE):
                error = ConflictError("ChatSurface Session already has an active Run")
                error.code = "active_run_conflict"
                error.run_id = run_id
                error.status = run_status
                error.target_type = authorized.binding.target_type
                raise error from exc

            active_request = await self.active_message_request(authorized)
            if active_request is not None:
                error = ConflictError(
                    "ChatSurface Session already has an active message request"
                )
                error.code = "active_message_request_conflict"
                error.target_type = authorized.binding.target_type
                raise error from exc

            try:
                return await super().begin_message(
                    authorized,
                    idempotency_key,
                    metadata=metadata,
                )
            except ConflictError as retry_exc:
                if str(retry_exc) != "ChatSurface Session already has an active Run":
                    raise
                error = ConflictError(
                    "ChatSurface Session already has an active message request"
                )
                error.code = "active_message_request_conflict"
                error.target_type = authorized.binding.target_type
                raise error from retry_exc

    async def latest_message_request(
        self,
        binding_id: UUID,
    ) -> ChatMessageRequestSnapshot | None:
        async with self._session_factory() as session:
            active = await session.scalar(
                select(ChatSurfaceMessageRequestModel)
                .where(
                    ChatSurfaceMessageRequestModel.session_binding_id == binding_id,
                    ChatSurfaceMessageRequestModel.status.in_(_MESSAGE_ACTIVE),
                )
                .order_by(
                    ChatSurfaceMessageRequestModel.created_at.desc(),
                    ChatSurfaceMessageRequestModel.id.desc(),
                )
                .limit(1)
            )
            model = active
            if model is None:
                model = await session.scalar(
                    select(ChatSurfaceMessageRequestModel)
                    .where(
                        ChatSurfaceMessageRequestModel.session_binding_id == binding_id
                    )
                    .order_by(
                        ChatSurfaceMessageRequestModel.created_at.desc(),
                        ChatSurfaceMessageRequestModel.id.desc(),
                    )
                    .limit(1)
                )
        if model is None:
            return None
        return ChatMessageRequestSnapshot(
            id=model.id,
            status=str(model.status),
            created_at=model.created_at,
            target_run_id=model.target_run_id,
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
        if run_status is None:
            # Message admission and Agent/Network Acceptance are separate durable
            # boundaries. A fresh request may legitimately precede its Run briefly,
            # but a request that never acquires canonical Run state must not keep the
            # partial-unique active-message gate forever.
            for _ in range(20):
                await asyncio.sleep(0.05)
                run_id, run_status = await self._resolve_request_run(
                    request,
                    authorized.binding,
                )
                if run_status is not None:
                    break

        if run_status is None:
            await super().mark_message(
                request.id,
                status="failed",
                target_run_id=run_id or request.target_run_id,
                error_code="run_acceptance_missing",
            )
            return None

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
        terminal_statuses = (
            _AGENT_TERMINAL if binding.target_type == "agent" else _NETWORK_TERMINAL
        )
        if (
            requested_terminal
            and original_status in _MESSAGE_ACTIVE
            and run_status not in terminal_statuses
        ):
            # Provider/Run persistence may lag the terminal SSE frame. Wait for the
            # canonical Run to become terminal instead of freezing the MessageRequest
            # in streaming merely because the first read still observed RUNNING.
            for _ in range(20):
                await asyncio.sleep(0.05)
                run_id, run_status = await self._resolve_request_run(request, binding)
                if run_status in terminal_statuses:
                    break

        if requested_terminal and run_status is not None:
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
