from __future__ import annotations

import asyncio
import time
from uuid import UUID

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select

from modules.network.application.service import NetworkApplicationService
from modules.network.domain.enums import NetworkEnvironment
from modules.network.infra.database.models import (
    NetworkExecutionModel,
    NetworkSessionModel,
)
from modules.network.presentation.reattach_routes import reattach_network_execution
from modules.network.presentation.routes import TERMINAL_STATUSES
from shared.infra.errors import (
    AuthorizationError,
    NotFoundError,
    RuntimeTimeoutError,
)
from shared.security.principal import ProjectApiPrincipal


class PublicNetworkRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=32768)
    session_id: UUID | None = None
    tenant_id: str | None = Field(default=None, max_length=128)
    user_id: str | None = Field(default=None, max_length=128)
    metadata: dict | None = None
    idempotency_key: str | None = Field(default=None, min_length=1, max_length=255)


def is_network_runtime_request(request: Request) -> bool:
    principal = getattr(request.state, "principal", None)
    return (
        isinstance(principal, ProjectApiPrincipal)
        and principal.kind == "runtime"
        and principal.target_type == "network"
    )


def _principal(request: Request) -> ProjectApiPrincipal:
    principal = getattr(request.state, "principal", None)
    if not isinstance(principal, ProjectApiPrincipal):
        raise AuthorizationError("Runtime Key authentication required")
    if (
        principal.kind != "runtime"
        or principal.target_type != "network"
        or principal.target_id is None
        or principal.environment is None
    ):
        raise AuthorizationError("Network Runtime Key binding is incomplete")
    return principal


def _service(request: Request) -> NetworkApplicationService:
    settings = request.app.state.settings
    return NetworkApplicationService(
        request.app.state.session_factory,
        hard_max_depth=settings.network_max_depth_hard,
        hard_max_invocations=settings.network_max_invocations_hard,
        hard_timeout_seconds=settings.network_timeout_hard_seconds,
    )


async def _payload(request: Request) -> PublicNetworkRunRequest:
    return PublicNetworkRunRequest(**(await request.json()))


async def _resolve_session(
    request: Request,
    principal: ProjectApiPrincipal,
    payload: PublicNetworkRunRequest,
) -> NetworkSessionModel:
    network_id = principal.target_id
    if network_id is None:
        raise AuthorizationError("Network Runtime Key binding is incomplete")
    environment = NetworkEnvironment(principal.environment)
    if environment == NetworkEnvironment.DRAFT:
        raise AuthorizationError("Runtime Keys cannot execute a Network Draft")

    if payload.session_id is None:
        return await _service(request).create_session(
            network_id=network_id,
            project_id=principal.project_id,
            environment=environment,
            title="Runtime session",
            tenant_id=payload.tenant_id or str(principal.project_id),
            user_id=payload.user_id,
            external_session_id=None,
        )

    async with request.app.state.session_factory() as database:
        network_session = await database.get(NetworkSessionModel, payload.session_id)
    if (
        network_session is None
        or network_session.network_id != network_id
        or network_session.project_id != principal.project_id
        or network_session.environment != environment.value
        or network_session.status != "active"
    ):
        raise NotFoundError("Network Session not found")
    return network_session


async def _submit(
    request: Request,
) -> tuple[ProjectApiPrincipal, NetworkSessionModel, NetworkExecutionModel]:
    principal = _principal(request)
    payload = await _payload(request)
    idempotency_key = payload.idempotency_key or request.headers.get("Idempotency-Key")
    network_id = principal.target_id
    if network_id is None:
        raise AuthorizationError("Network Runtime Key binding is incomplete")

    if idempotency_key:
        async with request.app.state.session_factory() as database:
            existing = await database.scalar(
                select(NetworkExecutionModel).where(
                    NetworkExecutionModel.network_id == network_id,
                    NetworkExecutionModel.idempotency_key == idempotency_key,
                )
            )
            existing_session = (
                await database.get(NetworkSessionModel, existing.network_session_id)
                if existing is not None
                else None
            )
        if existing is not None and existing_session is not None:
            if (
                existing.project_id != principal.project_id
                or existing_session.environment != principal.environment
            ):
                raise NotFoundError("Network execution not found")
            return principal, existing_session, existing

    network_session = await _resolve_session(request, principal, payload)
    execution = await _service(request).submit_execution(
        network_id=network_id,
        project_id=principal.project_id,
        network_session_id=network_session.id,
        message=payload.message,
        idempotency_key=idempotency_key,
    )
    return principal, network_session, execution


def _execution_payload(
    execution: NetworkExecutionModel,
    network_session: NetworkSessionModel,
) -> dict:
    return {
        "execution_id": str(execution.id),
        "job_id": str(execution.id),
        "session_id": str(network_session.id),
        "network_id": str(execution.network_id),
        "network_version_id": str(execution.network_version_id)
        if execution.network_version_id
        else None,
        "status": execution.status,
        "answer": execution.output_message,
        "result": execution.parsed_output
        if execution.parsed_output is not None
        else execution.output_message,
        "parsed_output": execution.parsed_output,
        "output_parse_error": execution.output_parse_error,
        "error": _public_failure_message(execution.failure_code),
        "trace_id": str(execution.root_trace_id) if execution.root_trace_id else None,
        "created_at": execution.created_at,
        "started_at": execution.started_at,
        "completed_at": execution.completed_at,
    }


def _public_failure_message(code: str | None) -> str | None:
    messages = {
        "credential_error": "The Agent provider credential is not ready.",
        "model_binding_error": "The Agent provider model binding is not ready.",
        "runtime_configuration_error": "The Agent runtime configuration is not ready.",
        "provider_rate_limited": "The model provider rate-limited this request.",
        "provider_timeout": "The model provider did not answer before the timeout.",
        "empty_model_output": "The Agent completed without producing a public result.",
        "budget_exceeded": "The Network runtime budget was exceeded.",
        "worker_lease_expired": "The Network worker stopped before completion.",
    }
    if code is None:
        return None
    return messages.get(code, "Network execution failed.")


async def run_network_http(request: Request):
    principal, network_session, submitted = await _submit(request)
    timeout_seconds = min(
        request.app.state.settings.runtime_total_timeout_seconds,
        request.app.state.settings.network_timeout_hard_seconds,
    )
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        async with request.app.state.session_factory() as database:
            execution = await database.get(NetworkExecutionModel, submitted.id)
        if execution is None or execution.project_id != principal.project_id:
            raise NotFoundError("Network execution not found")
        if execution.status == "completed":
            return {
                "success": True,
                "message": "ok",
                "data": _execution_payload(execution, network_session),
            }
        if execution.status in TERMINAL_STATUSES:
            status_code = 409 if execution.status == "cancelled" else 503
            return JSONResponse(
                status_code=status_code,
                content=jsonable_encoder(
                    {
                        "success": False,
                        "message": _public_failure_message(execution.failure_code)
                        or execution.status,
                        "data": _execution_payload(execution, network_session),
                    }
                ),
            )
        await asyncio.sleep(0.25)
    raise RuntimeTimeoutError("Network execution exceeded the HTTP response timeout")


async def stream_network_http(request: Request) -> StreamingResponse:
    _, _, execution = await _submit(request)
    # Create-and-observe and reattach intentionally share the same canonical stream.
    return await reattach_network_execution(execution.id, request)


async def create_network_job(request: Request):
    _, network_session, execution = await _submit(request)
    return {
        "success": True,
        "message": "Network job created",
        "data": _execution_payload(execution, network_session),
    }


async def get_network_job(request: Request):
    principal = _principal(request)
    job_id = UUID(str(request.path_params["job_id"]))
    async with request.app.state.session_factory() as database:
        execution = await database.get(NetworkExecutionModel, job_id)
        network_session = (
            await database.get(NetworkSessionModel, execution.network_session_id)
            if execution is not None
            else None
        )
    if (
        execution is None
        or network_session is None
        or execution.project_id != principal.project_id
        or execution.network_id != principal.target_id
        or network_session.environment != principal.environment
    ):
        raise NotFoundError("Network job not found")
    return {
        "success": True,
        "message": "ok",
        "data": _execution_payload(execution, network_session),
    }
