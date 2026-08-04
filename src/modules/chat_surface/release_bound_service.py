from __future__ import annotations

import secrets
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    SessionModel,
)
from modules.agent.infra.database.release_activation_repository import (
    AgentReleaseActivationModel,
)
from modules.chat_surface.infra.database.models import (
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.presentation.schemas import (
    CreateChatSurfaceRequest,
    CreateSurfaceSessionRequest,
    normalize_appearance_config,
)
from modules.chat_surface.security import normalize_origin
from modules.chat_surface.service import (
    AuthorizedChatSession,
    ChatSurfaceService as BaseChatSurfaceService,
    SurfaceCredential,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.network.infra.database.models import (
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from shared.runtime_environment import assert_runtime_environment_enabled


def surface_payload(surface: ChatSurfaceModel) -> dict:
    return {
        "id": str(surface.id),
        "public_id": surface.public_id,
        "project_id": str(surface.project_id),
        "name": surface.name,
        "description": surface.description,
        "target_type": surface.target_type,
        "target_id": str(surface.target_id),
        "target_release_id": str(surface.target_release_id),
        "environment": surface.environment,
        "status": surface.status,
        "access_mode": surface.access_mode,
        "allowed_origins": list(surface.allowed_origins or []),
        "appearance_config": normalize_appearance_config(
            dict(surface.appearance_config or {})
        ),
        "requests_per_minute": surface.requests_per_minute,
        "max_concurrent_runs": surface.max_concurrent_runs,
        "session_token_ttl_seconds": surface.session_token_ttl_seconds,
        "token_epoch": surface.token_epoch,
        "activated_at": surface.activated_at,
        "archived_at": surface.archived_at,
        "created_at": surface.created_at,
        "updated_at": surface.updated_at,
    }


class ChatSurfaceService(BaseChatSurfaceService):
    """Completes ChatSurface around immutable Agent and Network releases."""

    async def _current_target_release(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        target_type: str,
        target_id: UUID,
    ) -> tuple[UUID, str]:
        if target_type == "agent":
            target = await session.get(AgentModel, target_id)
        else:
            target = await session.get(NetworkModel, target_id)
        if target is None or target.project_id != project_id:
            raise NotFoundError(f"{target_type.capitalize()} not found")

        await assert_runtime_environment_enabled(
            session,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            environment="production",
        )

        if target_type == "agent":
            release_id = await session.scalar(
                select(AgentReleaseActivationModel.release_id)
                .where(
                    AgentReleaseActivationModel.project_id == project_id,
                    AgentReleaseActivationModel.agent_id == target_id,
                )
                .order_by(
                    AgentReleaseActivationModel.created_at.desc(),
                    AgentReleaseActivationModel.id.desc(),
                )
                .limit(1)
            )
            if release_id is None:
                release_id = await session.scalar(
                    select(AgentReleaseModel.id)
                    .where(
                        AgentReleaseModel.project_id == project_id,
                        AgentReleaseModel.agent_id == target_id,
                        AgentReleaseModel.status == "production",
                    )
                    .order_by(
                        AgentReleaseModel.updated_at.desc(),
                        AgentReleaseModel.created_at.desc(),
                        AgentReleaseModel.id.desc(),
                    )
                    .limit(1)
                )
            if release_id is None:
                raise ConflictError("Agent Production is not ready")
            release = await session.get(AgentReleaseModel, release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.agent_id != target_id
            ):
                raise ConflictError("Agent Production release was not found")
            return release.id, release.version

        release_id = target.production_version_id
        if release_id is None:
            raise ConflictError("Network Production is not ready")
        release = await session.get(NetworkVersionModel, release_id)
        if (
            release is None
            or release.project_id != project_id
            or release.network_id != target_id
            or release.kind != "release"
        ):
            raise ConflictError("Network Production release was not found")
        return release.id, release.version

    async def _bound_target_release(
        self,
        session: AsyncSession,
        *,
        project_id: UUID,
        target_type: str,
        target_id: UUID,
        target_release_id: UUID,
    ) -> tuple[UUID, str]:
        await assert_runtime_environment_enabled(
            session,
            target_type=target_type,
            target_id=target_id,
            project_id=project_id,
            environment="production",
        )
        if target_type == "agent":
            release = await session.get(AgentReleaseModel, target_release_id)
            if (
                release is None
                or release.project_id != project_id
                or release.agent_id != target_id
                or release.status in {"draft", "staging"}
            ):
                raise ConflictError("Pinned Agent Release is unavailable")
            return release.id, release.version

        release = await session.get(NetworkVersionModel, target_release_id)
        if (
            release is None
            or release.project_id != project_id
            or release.network_id != target_id
            or release.kind != "release"
        ):
            raise ConflictError("Pinned Network Release is unavailable")
        return release.id, release.version

    @staticmethod
    def _require_surface_credential(
        surface: ChatSurfaceModel,
        credential: SurfaceCredential,
    ) -> None:
        if (
            credential.project_id != surface.project_id
            or credential.chat_surface_id != surface.id
        ):
            raise AuthenticationError("Invalid ChatSurface Access Key")

    async def create_surface(
        self,
        *,
        project_id: UUID,
        actor_id: UUID,
        payload: CreateChatSurfaceRequest,
    ) -> ChatSurfaceModel:
        origins = self._origins(payload.allowed_origins)
        normalized_name = payload.name.casefold()
        async with self._session_factory() as session, session.begin():
            target_release_id, _ = await self._current_target_release(
                session,
                project_id=project_id,
                target_type=payload.target_type,
                target_id=payload.target_id,
            )
            surface = ChatSurfaceModel(
                public_id=f"csf_{secrets.token_urlsafe(12).rstrip('=')}",
                project_id=project_id,
                name=payload.name,
                normalized_name=normalized_name,
                description=payload.description,
                target_type=payload.target_type,
                target_id=payload.target_id,
                target_release_id=target_release_id,
                environment="production",
                status="draft",
                access_mode="backend_managed",
                allowed_origins=origins,
                appearance_config=payload.appearance_config,
                requests_per_minute=payload.requests_per_minute,
                max_concurrent_runs=payload.max_concurrent_runs,
                session_token_ttl_seconds=payload.session_token_ttl_seconds,
                token_epoch=1,
                created_by=actor_id,
            )
            session.add(surface)
            try:
                await session.flush()
            except IntegrityError as exc:
                raise ConflictError(
                    "A ChatSurface with this name already exists in the Project"
                ) from exc
            return surface

    async def refresh_target_release(self, surface_id: UUID) -> ChatSurfaceModel:
        async with self._session_factory() as session, session.begin():
            surface = await session.get(
                ChatSurfaceModel,
                surface_id,
                with_for_update=True,
            )
            if surface is None:
                raise NotFoundError("ChatSurface not found")
            if surface.status == "archived":
                raise ConflictError("Archived ChatSurface cannot change Release")
            release_id, _ = await self._current_target_release(
                session,
                project_id=surface.project_id,
                target_type=surface.target_type,
                target_id=surface.target_id,
            )
            surface.target_release_id = release_id
            return surface

    async def set_status(
        self,
        surface_id: UUID,
        status: str,
    ) -> ChatSurfaceModel:
        if status not in {"active", "disabled", "archived"}:
            raise ValidationError("Invalid ChatSurface status transition")
        async with self._session_factory() as session, session.begin():
            surface = await session.get(
                ChatSurfaceModel,
                surface_id,
                with_for_update=True,
            )
            if surface is None:
                raise NotFoundError("ChatSurface not found")
            if surface.status == "archived":
                raise ConflictError("Archived ChatSurface cannot be reactivated")
            if status == "active":
                if not surface.allowed_origins:
                    raise ConflictError(
                        "Active ChatSurface requires at least one allowed origin"
                    )
                await self._bound_target_release(
                    session,
                    project_id=surface.project_id,
                    target_type=surface.target_type,
                    target_id=surface.target_id,
                    target_release_id=surface.target_release_id,
                )
                surface.activated_at = datetime.now(UTC)
            elif status == "archived":
                surface.archived_at = datetime.now(UTC)
                surface.token_epoch += 1
            elif status == "disabled":
                surface.token_epoch += 1
            surface.status = status
            return surface

    async def create_session(
        self,
        *,
        surface: ChatSurfaceModel,
        credential: SurfaceCredential,
        idempotency_key: str,
        payload: CreateSurfaceSessionRequest,
    ) -> ChatSurfaceSessionBindingModel:
        credential.require("surface:sessions:create")
        self._require_surface_credential(surface, credential)
        if surface.status != "active":
            raise ConflictError("ChatSurface is not active")
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 255:
            raise ValidationError("A valid Idempotency-Key is required")
        metadata = self._metadata(payload.metadata)

        try:
            async with self._session_factory() as session, session.begin():
                existing = await session.scalar(
                    select(ChatSurfaceSessionBindingModel).where(
                        ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                        ChatSurfaceSessionBindingModel.idempotency_key
                        == normalized_key,
                    )
                )
                if existing is not None:
                    return existing

                locked_surface = await session.get(
                    ChatSurfaceModel,
                    surface.id,
                    with_for_update=True,
                )
                if locked_surface is None or locked_surface.status != "active":
                    raise ConflictError("ChatSurface is not active")
                self._require_surface_credential(locked_surface, credential)
                release_id, release_version = await self._bound_target_release(
                    session,
                    project_id=locked_surface.project_id,
                    target_type=locked_surface.target_type,
                    target_id=locked_surface.target_id,
                    target_release_id=locked_surface.target_release_id,
                )

                if locked_surface.target_type == "agent":
                    target_session = SessionModel(
                        project_id=locked_surface.project_id,
                        agent_id=locked_surface.target_id,
                        runtime_environment="production",
                        opened_release_id=release_id,
                        external_session_id=None,
                        tenant_id=str(locked_surface.id),
                        user_id=None,
                        status="active",
                        mode="chat",
                        data={
                            "source": "chat_surface",
                            "chat_surface_id": str(locked_surface.id),
                            "runtime_environment": "production",
                            "loaded_release_id": str(release_id),
                            "release_version": release_version,
                        },
                        last_message_at=None,
                        chat_surface_id=locked_surface.id,
                        origin="chat_surface",
                    )
                else:
                    target_session = NetworkSessionModel(
                        network_id=locked_surface.target_id,
                        network_version_id=release_id,
                        project_id=locked_surface.project_id,
                        environment="production",
                        title="ChatSurface session",
                        tenant_id=str(locked_surface.id),
                        user_id=None,
                        external_session_id=None,
                        status="active",
                        chat_surface_id=locked_surface.id,
                        origin="chat_surface",
                    )
                session.add(target_session)
                await session.flush()

                binding = ChatSurfaceSessionBindingModel(
                    chat_surface_id=locked_surface.id,
                    project_id=locked_surface.project_id,
                    target_type=locked_surface.target_type,
                    target_id=locked_surface.target_id,
                    target_release_id=release_id,
                    session_id=target_session.id,
                    surface_credential_id=credential.api_key_id,
                    idempotency_key=normalized_key,
                    external_reference=payload.external_reference,
                    metadata_=metadata,
                    status="active",
                )
                session.add(binding)
                await session.flush()
                return binding
        except IntegrityError:
            async with self._session_factory() as session:
                existing = await session.scalar(
                    select(ChatSurfaceSessionBindingModel).where(
                        ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                        ChatSurfaceSessionBindingModel.idempotency_key
                        == normalized_key,
                    )
                )
                if existing is not None:
                    return existing
            raise

    async def issue_session_token(
        self,
        *,
        surface: ChatSurfaceModel,
        credential: SurfaceCredential,
        session_id: UUID,
        origin: str,
    ) -> tuple[str, ChatSurfaceSessionBindingModel]:
        credential.require("surface:sessions:token:issue")
        self._require_surface_credential(surface, credential)
        normalized_origin = normalize_origin(
            origin,
            allow_insecure=self._allow_insecure_origins,
        )
        if normalized_origin not in set(surface.allowed_origins or []):
            raise AuthorizationError("Origin is not allowed by this ChatSurface")
        if surface.status != "active":
            raise ConflictError("ChatSurface is not active")

        binding = await self.get_binding(
            surface_id=surface.id,
            session_id=session_id,
        )
        if (
            binding.status != "active"
            or binding.project_id != surface.project_id
            or binding.target_type != surface.target_type
            or binding.target_id != surface.target_id
        ):
            raise ConflictError("ChatSurface Session is not active")

        token = self._token_codec.issue(
            project_id=surface.project_id,
            chat_surface_id=surface.id,
            target_type=surface.target_type,
            target_id=surface.target_id,
            target_release_id=binding.target_release_id,
            session_id=binding.session_id,
            origin=normalized_origin,
            surface_credential_id=credential.api_key_id,
            token_epoch=surface.token_epoch,
            ttl_seconds=surface.session_token_ttl_seconds,
        )
        return token, binding

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
        if host_origin:
            normalized = normalize_origin(
                host_origin,
                allow_insecure=self._allow_insecure_origins,
            )
            if normalized != claims.origin:
                raise AuthorizationError("ChatSurface Session origin does not match")

        async with self._session_factory() as session:
            surface = await session.get(ChatSurfaceModel, claims.chat_surface_id)
            if (
                surface is None
                or surface.status != "active"
                or surface.project_id != claims.project_id
                or surface.target_type != claims.target_type
                or surface.target_id != claims.target_id
                or surface.token_epoch != claims.token_epoch
                or claims.origin not in set(surface.allowed_origins or [])
            ):
                raise AuthenticationError("ChatSurface Session token is inactive")

            await assert_runtime_environment_enabled(
                session,
                target_type=surface.target_type,
                target_id=surface.target_id,
                project_id=surface.project_id,
                environment="production",
            )

            binding = await session.scalar(
                select(ChatSurfaceSessionBindingModel).where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                    ChatSurfaceSessionBindingModel.project_id == claims.project_id,
                    ChatSurfaceSessionBindingModel.session_id == claims.session_id,
                    ChatSurfaceSessionBindingModel.target_type == claims.target_type,
                    ChatSurfaceSessionBindingModel.target_id == claims.target_id,
                    ChatSurfaceSessionBindingModel.target_release_id
                    == claims.target_release_id,
                    ChatSurfaceSessionBindingModel.status == "active",
                )
            )
            if binding is None:
                raise NotFoundError("ChatSurface Session not found")

            credential = await session.get(
                ApiKeyModel,
                claims.surface_credential_id,
            )
            credential_expires_at = (
                credential.expires_at if credential is not None else None
            )
            if (
                credential_expires_at is not None
                and credential_expires_at.tzinfo is None
            ):
                credential_expires_at = credential_expires_at.replace(tzinfo=UTC)
            if (
                credential is None
                or credential.kind != "chat_surface"
                or credential.project_id != surface.project_id
                or credential.chat_surface_id != surface.id
                or credential.status != "active"
                or credential.revoked_at is not None
                or (
                    credential_expires_at is not None
                    and credential_expires_at <= datetime.now(UTC)
                )
            ):
                raise AuthenticationError("ChatSurface Session token is inactive")

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

    def embed_configuration(self, authorized: AuthorizedChatSession) -> dict:
        return {
            "surface_id": authorized.surface.public_id,
            "name": authorized.surface.name,
            "appearance": normalize_appearance_config(
                dict(authorized.surface.appearance_config or {})
            ),
            "protocol_version": 1,
        }


__all__ = ["ChatSurfaceService", "surface_payload"]
