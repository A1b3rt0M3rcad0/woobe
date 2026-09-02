from __future__ import annotations

from uuid import UUID, uuid4

from modules.chat_surface.presentation.schemas import CreateSurfaceSessionRequest
from modules.chat_surface.security import normalize_origin
from modules.chat_surface.service import ChatSurfaceService, SurfaceCredential
from shared.contracts.errors import ConflictError


CONTROL_PLANE_TEST_SOURCE = "control_plane_test"


class ControlPlaneChatSurfaceService(ChatSurfaceService):
    """Adds the Control Plane test-Session flow to the ChatSurface service."""

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
            raise ConflictError(
                "ChatSurface became inactive while creating the test Session"
            )

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


__all__ = ["CONTROL_PLANE_TEST_SOURCE", "ControlPlaneChatSurfaceService"]
