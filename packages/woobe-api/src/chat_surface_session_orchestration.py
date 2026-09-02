from __future__ import annotations

from uuid import UUID

from modules.agent.entrypoint import (
    build_agent_chat_surface_target_release_reader,
    close_agent_chat_surface_session_composer,
    create_agent_chat_surface_session_composer,
)
from modules.chat_surface.entrypoint import (
    archive_chat_surface_session_binding_composer,
    create_chat_surface_session_binding_composer,
    get_chat_surface_session_binding_composer,
    get_chat_surface_session_by_idempotency_composer,
)
from modules.network.entrypoint import (
    build_network_chat_surface_target_release_reader,
    close_network_chat_surface_session_composer,
    create_network_chat_surface_session_composer,
)
from shared.contracts.errors import NotFoundError
from shared.presentation.http.request import Request as InternalRequest


async def _validated_release(surface: dict):
    project_id = UUID(str(surface["project_id"]))
    target_id = UUID(str(surface["target_id"]))
    release_id = UUID(str(surface["target_release_id"]))
    if surface["target_type"] == "agent":
        return await build_agent_chat_surface_target_release_reader().validate(
            project_id=project_id,
            target_id=target_id,
            release_id=release_id,
        )
    return await build_network_chat_surface_target_release_reader().validate(
        project_id=project_id,
        target_id=target_id,
        release_id=release_id,
    )


async def _create_target_session(surface: dict) -> dict:
    release = await _validated_release(surface)
    project_id = str(surface["project_id"])
    target_id = str(surface["target_id"])
    release_id = str(surface["target_release_id"])
    chat_surface_id = str(surface["id"])
    if surface["target_type"] == "agent":
        response = await create_agent_chat_surface_session_composer()(
            InternalRequest(
                body={
                    "project_id": project_id,
                    "agent_id": target_id,
                    "agent_release_id": release_id,
                    "release_version": release.version,
                    "chat_surface_id": chat_surface_id,
                }
            )
        )
    else:
        response = await create_network_chat_surface_session_composer()(
            InternalRequest(
                body={
                    "project_id": project_id,
                    "network_id": target_id,
                    "network_version_id": release_id,
                    "chat_surface_id": chat_surface_id,
                }
            )
        )
    return dict(response.body["data"])


async def close_target_session(
    *,
    surface: dict,
    binding: dict,
    ignore_missing: bool = False,
) -> None:
    body = {
        "project_id": str(surface["project_id"]),
        "chat_surface_id": str(surface["id"]),
        "session_id": str(binding["session_id"]),
    }
    try:
        if binding["target_type"] == "agent":
            await close_agent_chat_surface_session_composer()(
                InternalRequest(
                    body={
                        **body,
                        "agent_id": str(binding["target_id"]),
                        "agent_release_id": str(binding["target_release_id"]),
                    }
                )
            )
        else:
            await close_network_chat_surface_session_composer()(
                InternalRequest(
                    body={
                        **body,
                        "network_id": str(binding["target_id"]),
                        "network_version_id": str(binding["target_release_id"]),
                    }
                )
            )
    except NotFoundError:
        if not ignore_missing:
            raise


async def get_binding(
    *,
    surface_id: UUID,
    session_id: UUID,
) -> dict:
    response = await get_chat_surface_session_binding_composer()(
        InternalRequest(
            path_params={
                "surface_id": str(surface_id),
                "session_id": str(session_id),
            }
        )
    )
    return dict(response.body["data"])


async def archive_bound_target_session(
    *,
    surface: dict,
    binding: dict,
) -> dict:
    await close_target_session(
        surface=surface,
        binding=binding,
        ignore_missing=True,
    )
    response = await archive_chat_surface_session_binding_composer()(
        InternalRequest(
            path_params={
                "surface_id": str(surface["id"]),
                "session_id": str(binding["session_id"]),
            }
        )
    )
    return dict(response.body["data"])


async def create_bound_target_session(
    *,
    surface: dict,
    surface_credential_id: UUID,
    idempotency_key: str,
    external_reference: str | None,
    metadata: dict | None,
) -> dict:
    surface_id = UUID(str(surface["id"]))
    existing_response = await get_chat_surface_session_by_idempotency_composer()(
        InternalRequest(
            path_params={"surface_id": str(surface_id)},
            body={"idempotency_key": idempotency_key},
        )
    )
    existing = existing_response.body["data"]
    if existing is not None:
        return dict(existing)

    target_session = await _create_target_session(surface)
    target_binding = {
        "chat_surface_id": str(surface_id),
        "session_id": str(target_session["id"]),
        "target_type": str(surface["target_type"]),
        "target_id": str(surface["target_id"]),
        "target_release_id": str(surface["target_release_id"]),
    }
    try:
        response = await create_chat_surface_session_binding_composer()(
            InternalRequest(
                path_params={"surface_id": str(surface_id)},
                body={
                    "expected_project_id": str(surface["project_id"]),
                    "expected_target_type": str(surface["target_type"]),
                    "expected_target_id": str(surface["target_id"]),
                    "expected_target_release_id": str(surface["target_release_id"]),
                    "session_id": str(target_session["id"]),
                    "surface_credential_id": str(surface_credential_id),
                    "idempotency_key": idempotency_key,
                    "external_reference": external_reference,
                    "metadata": metadata,
                },
            )
        )
        binding = dict(response.body["data"])
    except Exception:
        try:
            await close_target_session(
                surface=surface,
                binding=target_binding,
                ignore_missing=True,
            )
        finally:
            raise

    if UUID(str(binding["session_id"])) != UUID(str(target_session["id"])):
        await close_target_session(
            surface=surface,
            binding=target_binding,
            ignore_missing=True,
        )
    return binding


__all__ = [
    "archive_bound_target_session",
    "close_target_session",
    "create_bound_target_session",
    "get_binding",
]
