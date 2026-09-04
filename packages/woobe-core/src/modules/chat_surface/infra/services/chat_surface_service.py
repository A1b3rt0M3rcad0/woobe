from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from uuid import UUID, uuid4

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from modules.agent.infra.database.models import (
    AgentModel,
    AgentReleaseModel,
    MessageModel,
    SessionModel,
)
from modules.agent.infra.database.release_activation_repository import (
    AgentReleaseActivationModel,
)
from modules.chat_surface.domain.enums import CHAT_SURFACE_KEY_SCOPES
from modules.chat_surface.infra.database.models import (
    ChatSurfaceMessageRequestModel,
    ChatSurfaceModel,
    ChatSurfaceSessionBindingModel,
)
from modules.chat_surface.application.dtos import (
    CreateChatSurfaceRequest,
    CreateSurfaceAccessKeyRequest,
    CreateSurfaceSessionRequest,
    UpdateChatSurfaceRequest,
    normalize_appearance_config,
)
from modules.chat_surface.application.security import (
    ChatSessionClaims,
    ChatSessionTokenCodec,
    normalize_origin,
)
from modules.core.infra.database.models import ApiKeyModel
from modules.network.infra.database.models import (
    NetworkMessageModel,
    NetworkModel,
    NetworkSessionModel,
    NetworkVersionModel,
)
from shared.infra.errors import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    RateLimitError,
    ValidationError,
)
from shared.runtime_environment import assert_runtime_environment_enabled
from shared.security.api_keys import (
    hash_api_key,
    issue_chat_surface_api_key,
    parse_project_api_key,
)


@dataclass(frozen=True, slots=True)
class SurfaceCredential:
    api_key_id: UUID
    project_id: UUID
    chat_surface_id: UUID
    scopes: frozenset[str]

    def require(self, scope: str) -> None:
        if scope not in self.scopes:
            raise AuthorizationError("ChatSurface Access Key scope is not sufficient")


@dataclass(frozen=True, slots=True)
class AuthorizedChatSession:
    surface: ChatSurfaceModel
    binding: ChatSurfaceSessionBindingModel
    claims: ChatSessionClaims


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


class ChatSurfaceService:
    """ChatSurface lifecycle bound to immutable Agent and Network Releases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        token_codec: ChatSessionTokenCodec,
        *,
        allow_insecure_origins: bool = False,
        max_metadata_bytes: int = 16_384,
    ) -> None:
        self._session_factory = session_factory
        self._token_codec = token_codec
        self._allow_insecure_origins = allow_insecure_origins
        self._max_metadata_bytes = max_metadata_bytes

    def _origins(self, origins: list[str]) -> list[str]:
        normalized = [
            normalize_origin(
                origin,
                allow_insecure=self._allow_insecure_origins,
            )
            for origin in origins
        ]
        return list(dict.fromkeys(normalized))

    def _metadata(self, value: dict | None) -> dict | None:
        if value is None:
            return None
        encoded = json.dumps(value, separators=(",", ":"), default=str).encode()
        if len(encoded) > self._max_metadata_bytes:
            raise ValidationError("ChatSurface metadata is too large")
        return value

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

    async def list_surfaces(self, project_id: UUID) -> list[ChatSurfaceModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatSurfaceModel)
                .where(ChatSurfaceModel.project_id == project_id)
                .order_by(ChatSurfaceModel.created_at.desc())
            )
            return list(result.scalars().all())

    async def get_surface(self, surface_id: UUID) -> ChatSurfaceModel:
        async with self._session_factory() as session:
            surface = await session.get(ChatSurfaceModel, surface_id)
            if surface is None:
                raise NotFoundError("ChatSurface not found")
            return surface

    async def update_surface(
        self,
        surface_id: UUID,
        payload: UpdateChatSurfaceRequest,
    ) -> ChatSurfaceModel:
        async with self._session_factory() as session, session.begin():
            surface = await session.get(
                ChatSurfaceModel,
                surface_id,
                with_for_update=True,
            )
            if surface is None:
                raise NotFoundError("ChatSurface not found")
            if surface.status == "archived":
                raise ConflictError("Archived ChatSurface cannot be changed")
            changes = payload.model_dump(exclude_unset=True)
            if "name" in changes:
                name = " ".join(str(changes["name"]).split())
                surface.name = name
                surface.normalized_name = name.casefold()
            if "description" in changes:
                surface.description = changes["description"]
            if "allowed_origins" in changes:
                surface.allowed_origins = self._origins(
                    changes["allowed_origins"] or []
                )
            if "appearance_config" in changes:
                surface.appearance_config = changes["appearance_config"] or {}
            for field in (
                "requests_per_minute",
                "max_concurrent_runs",
                "session_token_ttl_seconds",
            ):
                if field in changes:
                    setattr(surface, field, changes[field])
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

    async def create_access_key(
        self,
        surface_id: UUID,
        *,
        actor_id: UUID,
        payload: CreateSurfaceAccessKeyRequest,
    ) -> tuple[ApiKeyModel, str, str]:
        async with self._session_factory() as session, session.begin():
            surface = await session.get(ChatSurfaceModel, surface_id)
            if surface is None:
                raise NotFoundError("ChatSurface not found")
            if surface.status == "archived":
                raise ConflictError("Archived ChatSurface cannot receive Access Keys")
            issued = issue_chat_surface_api_key()
            credential_id = uuid4()
            api_key = ApiKeyModel(
                project_id=surface.project_id,
                credential_id=credential_id,
                name=payload.name,
                description=payload.description,
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                scopes=sorted(CHAT_SURFACE_KEY_SCOPES),
                kind="chat_surface",
                agent_id=None,
                target_type=None,
                target_id=None,
                chat_surface_id=surface.id,
                environment=None,
                interfaces=[],
                status="active",
                created_by_user_id=actor_id,
            )
            session.add(api_key)
            await session.flush()
            return api_key, issued.value, issued.display_prefix

    async def list_access_keys(self, surface_id: UUID) -> list[ApiKeyModel]:
        async with self._session_factory() as session:
            result = await session.execute(
                select(ApiKeyModel)
                .where(
                    ApiKeyModel.chat_surface_id == surface_id,
                    ApiKeyModel.kind == "chat_surface",
                )
                .order_by(ApiKeyModel.created_at.desc())
            )
            return list(result.scalars().all())

    async def revoke_access_key(
        self,
        surface_id: UUID,
        api_key_id: UUID,
    ) -> ApiKeyModel:
        async with self._session_factory() as session, session.begin():
            api_key = await session.get(ApiKeyModel, api_key_id, with_for_update=True)
            if (
                api_key is None
                or api_key.chat_surface_id != surface_id
                or api_key.kind != "chat_surface"
            ):
                raise NotFoundError("ChatSurface Access Key not found")
            api_key.status = "revoked"
            api_key.revoked_at = datetime.now(UTC)
            return api_key

    async def rotate_access_key(
        self,
        surface_id: UUID,
        api_key_id: UUID,
        *,
        actor_id: UUID,
    ) -> tuple[ApiKeyModel, str, str]:
        async with self._session_factory() as session, session.begin():
            current = await session.get(
                ApiKeyModel,
                api_key_id,
                with_for_update=True,
            )
            if (
                current is None
                or current.chat_surface_id != surface_id
                or current.kind != "chat_surface"
            ):
                raise NotFoundError("ChatSurface Access Key not found")
            if current.status != "active" or current.revoked_at is not None:
                raise ConflictError("Only active ChatSurface Access Keys can rotate")
            issued = issue_chat_surface_api_key()
            now = datetime.now(UTC)
            current.status = "revoked"
            current.revoked_at = now
            replacement = ApiKeyModel(
                project_id=current.project_id,
                credential_id=current.credential_id,
                name=current.name,
                description=current.description,
                key_prefix=issued.public_prefix,
                key_hash=issued.digest,
                key_version=issued.key_version,
                scopes=list(current.scopes or []),
                kind="chat_surface",
                agent_id=None,
                target_type=None,
                target_id=None,
                chat_surface_id=surface_id,
                environment=None,
                interfaces=[],
                status="active",
                expires_at=current.expires_at,
                created_by_user_id=actor_id,
                rotated_from_id=current.id,
            )
            session.add(replacement)
            await session.flush()
            return replacement, issued.value, issued.display_prefix

    async def authenticate_access_key(
        self,
        *,
        public_id: str,
        credentials: str,
    ) -> tuple[ChatSurfaceModel, SurfaceCredential]:
        parsed = parse_project_api_key(credentials)
        if (
            parsed is None
            or parsed.kind != "chat_surface"
            or parsed.environment is not None
        ):
            raise AuthenticationError("Invalid ChatSurface Access Key")
        supplied_digest = hash_api_key(credentials)
        now = datetime.now(UTC)
        async with self._session_factory() as session:
            surface = await session.scalar(
                select(ChatSurfaceModel).where(
                    ChatSurfaceModel.public_id == public_id
                )
            )
            if surface is None:
                raise AuthenticationError("Invalid ChatSurface Access Key")
            result = await session.execute(
                select(ApiKeyModel).where(
                    ApiKeyModel.key_prefix == parsed.public_prefix,
                    ApiKeyModel.key_version == parsed.key_version,
                    ApiKeyModel.chat_surface_id == surface.id,
                    ApiKeyModel.kind == "chat_surface",
                )
            )
            api_key = None
            for candidate in result.scalars().all():
                if compare_digest(bytes(candidate.key_hash), supplied_digest):
                    api_key = candidate
                    break
            if api_key is None:
                raise AuthenticationError("Invalid ChatSurface Access Key")
            expires_at = api_key.expires_at
            if expires_at is not None and expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=UTC)
            if (
                api_key.status != "active"
                or api_key.revoked_at is not None
                or (expires_at is not None and expires_at <= now)
            ):
                raise AuthenticationError("ChatSurface Access Key is inactive")
            api_key.last_used_at = now
            await session.commit()
            return surface, SurfaceCredential(
                api_key_id=api_key.id,
                project_id=api_key.project_id,
                chat_surface_id=surface.id,
                scopes=frozenset(str(scope) for scope in (api_key.scopes or [])),
            )

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

    async def get_binding(
        self,
        *,
        surface_id: UUID,
        session_id: UUID,
    ) -> ChatSurfaceSessionBindingModel:
        async with self._session_factory() as session:
            binding = await session.scalar(
                select(ChatSurfaceSessionBindingModel).where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                    ChatSurfaceSessionBindingModel.session_id == session_id,
                )
            )
            if binding is None:
                raise NotFoundError("ChatSurface Session not found")
            return binding

    async def list_sessions(
        self,
        surface_id: UUID,
        *,
        limit: int = 50,
    ) -> list[ChatSurfaceSessionBindingModel]:
        safe_limit = min(100, max(1, limit))
        async with self._session_factory() as session:
            result = await session.execute(
                select(ChatSurfaceSessionBindingModel)
                .where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface_id
                )
                .order_by(ChatSurfaceSessionBindingModel.updated_at.desc())
                .limit(safe_limit)
            )
            return list(result.scalars().all())

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

    async def archive_session(
        self,
        *,
        surface: ChatSurfaceModel,
        credential: SurfaceCredential,
        session_id: UUID,
    ) -> ChatSurfaceSessionBindingModel:
        credential.require("surface:sessions:archive")
        self._require_surface_credential(surface, credential)
        async with self._session_factory() as session, session.begin():
            binding = await session.scalar(
                select(ChatSurfaceSessionBindingModel)
                .where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                    ChatSurfaceSessionBindingModel.session_id == session_id,
                )
                .with_for_update()
            )
            if binding is None:
                raise NotFoundError("ChatSurface Session not found")
            binding.status = "archived"
            if binding.target_type == "agent":
                target_session = await session.get(SessionModel, session_id)
            else:
                target_session = await session.get(NetworkSessionModel, session_id)
            if target_session is not None:
                target_session.status = (
                    "closed" if binding.target_type == "agent" else "archived"
                )
            return binding

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

    async def list_messages(
        self,
        authorized: AuthorizedChatSession,
        *,
        limit: int,
        cursor: UUID | None,
    ) -> dict:
        safe_limit = min(100, max(1, limit))
        async with self._session_factory() as session:
            if authorized.binding.target_type == "agent":
                model = MessageModel
                session_column = MessageModel.session_id
            else:
                model = NetworkMessageModel
                session_column = NetworkMessageModel.network_session_id
            statement = select(model).where(
                session_column == authorized.binding.session_id
            )
            if cursor is not None:
                statement = statement.where(model.id < cursor)
            result = await session.execute(
                statement.order_by(model.id.desc()).limit(safe_limit + 1)
            )
            items = list(result.scalars().all())
            has_next = len(items) > safe_limit
            visible = items[:safe_limit]
            visible.reverse()
            return {
                "items": [
                    {
                        "id": str(message.id),
                        "role": message.role,
                        "content": message.content,
                        "data": message.data,
                        "created_at": message.created_at,
                    }
                    for message in visible
                ],
                "next_cursor": (
                    str(items[safe_limit - 1].id)
                    if has_next and len(items) >= safe_limit
                    else None
                ),
                "has_next": has_next,
            }

    async def begin_message(
        self,
        authorized: AuthorizedChatSession,
        idempotency_key: str,
        *,
        metadata: dict | None = None,
    ) -> tuple[ChatSurfaceMessageRequestModel, bool]:
        normalized_key = idempotency_key.strip()
        if not normalized_key or len(normalized_key) > 255:
            raise ValidationError("A valid Idempotency-Key is required")
        self._metadata(metadata)
        try:
            async with self._session_factory() as session, session.begin():
                stale_before = datetime.now(UTC) - timedelta(minutes=10)
                await session.execute(
                    update(ChatSurfaceMessageRequestModel)
                    .where(
                        ChatSurfaceMessageRequestModel.session_binding_id
                        == authorized.binding.id,
                        ChatSurfaceMessageRequestModel.status.in_(
                            {"accepted", "streaming"}
                        ),
                        ChatSurfaceMessageRequestModel.updated_at < stale_before,
                    )
                    .values(
                        status="failed",
                        error_code="runtime_lease_expired",
                        completed_at=datetime.now(UTC),
                    )
                )
                existing = await session.scalar(
                    select(ChatSurfaceMessageRequestModel).where(
                        ChatSurfaceMessageRequestModel.session_binding_id
                        == authorized.binding.id,
                        ChatSurfaceMessageRequestModel.idempotency_key
                        == normalized_key,
                    )
                )
                if existing is not None:
                    return existing, False
                surface = await session.get(
                    ChatSurfaceModel,
                    authorized.surface.id,
                    with_for_update=True,
                )
                if surface is None or surface.status != "active":
                    raise ConflictError("ChatSurface is not active")
                one_minute_ago = datetime.now(UTC) - timedelta(minutes=1)
                surface_requests = await session.scalar(
                    select(func.count(ChatSurfaceMessageRequestModel.id))
                    .join(
                        ChatSurfaceSessionBindingModel,
                        ChatSurfaceSessionBindingModel.id
                        == ChatSurfaceMessageRequestModel.session_binding_id,
                    )
                    .where(
                        ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                        ChatSurfaceMessageRequestModel.created_at >= one_minute_ago,
                    )
                )
                if int(surface_requests or 0) >= surface.requests_per_minute:
                    raise RateLimitError(
                        "ChatSurface request rate limit exceeded",
                        retry_after=60,
                    )
                session_requests = await session.scalar(
                    select(func.count(ChatSurfaceMessageRequestModel.id)).where(
                        ChatSurfaceMessageRequestModel.session_binding_id
                        == authorized.binding.id,
                        ChatSurfaceMessageRequestModel.created_at >= one_minute_ago,
                    )
                )
                if int(session_requests or 0) >= 30:
                    raise RateLimitError(
                        "ChatSurface Session message rate limit exceeded",
                        retry_after=60,
                    )
                active_runs = await session.scalar(
                    select(func.count(ChatSurfaceMessageRequestModel.id))
                    .join(
                        ChatSurfaceSessionBindingModel,
                        ChatSurfaceSessionBindingModel.id
                        == ChatSurfaceMessageRequestModel.session_binding_id,
                    )
                    .where(
                        ChatSurfaceSessionBindingModel.chat_surface_id == surface.id,
                        ChatSurfaceMessageRequestModel.status.in_(
                            {"accepted", "streaming"}
                        ),
                    )
                )
                if int(active_runs or 0) >= surface.max_concurrent_runs:
                    raise RateLimitError(
                        "ChatSurface concurrency limit exceeded",
                        retry_after=1,
                    )
                request = ChatSurfaceMessageRequestModel(
                    session_binding_id=authorized.binding.id,
                    idempotency_key=normalized_key,
                    status="accepted",
                )
                session.add(request)
                await session.flush()
                return request, True
        except IntegrityError as exc:
            async with self._session_factory() as session:
                existing = await session.scalar(
                    select(ChatSurfaceMessageRequestModel).where(
                        ChatSurfaceMessageRequestModel.session_binding_id
                        == authorized.binding.id,
                        ChatSurfaceMessageRequestModel.idempotency_key
                        == normalized_key,
                    )
                )
                if existing is not None:
                    return existing, False
            raise ConflictError(
                "ChatSurface Session already has an active Run"
            ) from exc

    async def mark_message(
        self,
        request_id: UUID,
        *,
        status: str,
        target_run_id: UUID | None = None,
        error_code: str | None = None,
    ) -> None:
        async with self._session_factory() as session, session.begin():
            request = await session.get(
                ChatSurfaceMessageRequestModel,
                request_id,
                with_for_update=True,
            )
            if request is None:
                return
            request.status = status
            request.target_run_id = target_run_id or request.target_run_id
            request.error_code = error_code
            if status in {"completed", "failed", "cancelled"}:
                request.completed_at = datetime.now(UTC)

    async def surface_activity(self, surface_id: UUID) -> dict:
        async with self._session_factory() as session:
            sessions = await session.scalar(
                select(func.count(ChatSurfaceSessionBindingModel.id)).where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface_id
                )
            )
            active = await session.scalar(
                select(func.count(ChatSurfaceSessionBindingModel.id)).where(
                    ChatSurfaceSessionBindingModel.chat_surface_id == surface_id,
                    ChatSurfaceSessionBindingModel.status == "active",
                )
            )
            return {
                "sessions": int(sessions or 0),
                "active_sessions": int(active or 0),
            }

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

