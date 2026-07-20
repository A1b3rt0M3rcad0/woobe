from __future__ import annotations

from uuid import UUID

from fastapi import Request
from sqlalchemy import select

from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkSessionModel,
)
from shared.infra.errors import NotFoundError
from shared.runtime_environment import assert_runtime_environment_enabled
from shared.security.principal import ProjectApiPrincipal


async def _existing_idempotent_execution(
    request: Request,
    *,
    network_id: UUID,
    idempotency_key: str | None,
) -> bool:
    if not idempotency_key:
        return False
    async with request.app.state.session_factory() as session:
        existing = await session.scalar(
            select(NetworkExecutionModel.id).where(
                NetworkExecutionModel.network_id == network_id,
                NetworkExecutionModel.idempotency_key == idempotency_key,
            )
        )
    return existing is not None


async def enforce_network_runtime_environment(request: Request) -> None:
    """Guard Network Session/Run admission while leaving management routes open."""

    if request.method != "POST":
        return
    network_id_value = request.path_params.get("network_id")
    if network_id_value is None:
        return
    path = request.url.path.rstrip("/")
    creates_session = path.endswith("/sessions")
    submits_execution = path.endswith("/executions/stream")
    if not creates_session and not submits_execution:
        return

    body = await request.json()
    network_id = UUID(str(network_id_value))
    project_id = UUID(str(body["project_id"]))

    if creates_session:
        environment = str(body["environment"])
    else:
        idempotency_key = body.get("idempotency_key") or request.headers.get(
            "Idempotency-Key"
        )
        if await _existing_idempotent_execution(
            request,
            network_id=network_id,
            idempotency_key=idempotency_key,
        ):
            return
        network_session_id = UUID(str(body["network_session_id"]))
        async with request.app.state.session_factory() as session:
            network_session = await session.get(NetworkSessionModel, network_session_id)
        if (
            network_session is None
            or network_session.network_id != network_id
            or network_session.project_id != project_id
        ):
            raise NotFoundError("Network Session not found")
        environment = network_session.environment

    async with request.app.state.session_factory() as session, session.begin():
        await assert_runtime_environment_enabled(
            session,
            target_type="network",
            target_id=network_id,
            project_id=project_id,
            environment=environment,
        )


async def enforce_public_network_runtime_environment(request: Request) -> None:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal):
        return
    if principal.target_type != "network" or principal.target_id is None:
        return
    if principal.environment is None:
        return

    body = await request.json()
    idempotency_key = body.get("idempotency_key") or request.headers.get(
        "Idempotency-Key"
    )
    if await _existing_idempotent_execution(
        request,
        network_id=principal.target_id,
        idempotency_key=idempotency_key,
    ):
        return

    async with request.app.state.session_factory() as session, session.begin():
        await assert_runtime_environment_enabled(
            session,
            target_type="network",
            target_id=principal.target_id,
            project_id=principal.project_id,
            environment=principal.environment,
        )
