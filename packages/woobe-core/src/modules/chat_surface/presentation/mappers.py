from modules.chat_surface.application.dtos.surface_read import ChatSurfaceState
from modules.chat_surface.presentation.schemas import normalize_appearance_config


def chat_surface_payload(surface: ChatSurfaceState) -> dict:
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
        "allowed_origins": list(surface.allowed_origins),
        "appearance_config": normalize_appearance_config(surface.appearance_config),
        "requests_per_minute": surface.requests_per_minute,
        "max_concurrent_runs": surface.max_concurrent_runs,
        "session_token_ttl_seconds": surface.session_token_ttl_seconds,
        "token_epoch": surface.token_epoch,
        "activated_at": surface.activated_at,
        "archived_at": surface.archived_at,
        "created_at": surface.created_at,
        "updated_at": surface.updated_at,
    }


__all__ = ["chat_surface_payload"]
