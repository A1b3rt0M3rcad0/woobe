from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from modules.agent.domain.release_compatibility import (
    effective_output_schema,
    normalize_output_schema,
    output_schemas_equivalent,
)
from modules.agent.infra.database.models import AgentReleaseModel
from modules.network.infra.database.models import NetworkModel
from modules.network.infra.database.schema_extensions import NetworkVersionModel
from shared.infra.database.session import create_session_factory
from shared.infra.errors import NotFoundError, ValidationError
from shared.security.principal import ProjectApiPrincipal


class OutputContextValidationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    output_context: dict[str, Any] | None = None


def _schema_hash(schema: dict[str, Any] | None) -> str:
    encoded = json.dumps(
        schema,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def _agent_contract(
    request: Request,
    principal: ProjectApiPrincipal,
) -> tuple[dict[str, Any] | None, str, str]:
    target_id = principal.target_id or principal.agent_id
    environment = principal.environment
    if target_id is None or environment not in {"staging", "production"}:
        raise ValidationError("Runtime Key binding is incomplete")

    session_factory = create_session_factory(request.app.state.async_engine)
    async with session_factory() as session:
        release = await session.scalar(
            select(AgentReleaseModel)
            .where(
                AgentReleaseModel.id.is_not(None),
                AgentReleaseModel.agent_id == target_id,
                AgentReleaseModel.project_id == principal.project_id,
                AgentReleaseModel.status == environment,
            )
            .order_by(AgentReleaseModel.created_at.desc())
            .limit(1)
        )
        if release is None:
            raise NotFoundError(
                f"Agent {environment} Release not found"
            )
        return effective_output_schema(release), str(release.id), str(release.version)


async def _network_contract(
    request: Request,
    principal: ProjectApiPrincipal,
) -> tuple[dict[str, Any] | None, str, str]:
    target_id = principal.target_id
    environment = principal.environment
    if target_id is None or environment not in {"staging", "production"}:
        raise ValidationError("Runtime Key binding is incomplete")

    session_factory = create_session_factory(request.app.state.async_engine)
    async with session_factory() as session:
        network = await session.scalar(
            select(NetworkModel).where(
                NetworkModel.id == target_id,
                NetworkModel.project_id == principal.project_id,
            )
        )
        if network is None:
            raise NotFoundError("Network not found")

        version_id = (
            network.staging_version_id
            if environment == "staging"
            else network.production_version_id
        )
        if version_id is None:
            raise NotFoundError(
                f"Network {environment} Release not found"
            )

        version = await session.get(NetworkVersionModel, version_id)
        if (
            version is None
            or version.network_id != target_id
            or version.project_id != principal.project_id
        ):
            raise NotFoundError("Network Release not found")

        contract = getattr(version, "public_output_contract", None)
        schema = (
            contract.get("schema")
            if isinstance(contract, dict)
            else None
        )
        return normalize_output_schema(schema), str(version.id), str(version.version)


async def validate_output_context(
    request: Request,
    principal: ProjectApiPrincipal,
    payload: OutputContextValidationRequest,
) -> dict[str, Any]:
    if principal.kind != "runtime":
        raise ValidationError("Runtime Key authentication required")

    if principal.target_type == "agent":
        expected, release_id, release_version = await _agent_contract(
            request,
            principal,
        )
    elif principal.target_type == "network":
        expected, release_id, release_version = await _network_contract(
            request,
            principal,
        )
    else:
        raise ValidationError("Runtime Key binding is incomplete")

    received = normalize_output_schema(payload.output_context)
    valid = output_schemas_equivalent(expected, received)

    return {
        "success": True,
        "data": {
            "valid": valid,
            "target_type": principal.target_type,
            "target_id": str(principal.target_id or principal.agent_id),
            "environment": principal.environment,
            "release_id": release_id,
            "release_version": release_version,
            "expected_output_context": expected,
            "received_output_context": received,
            "expected_hash": _schema_hash(expected),
            "received_hash": _schema_hash(received),
            "issues": [] if valid else [
                {
                    "code": "OUTPUT_CONTEXT_MISMATCH",
                    "message": (
                        "SDK output_context does not match the published "
                        "Woobe Output Contract"
                    ),
                }
            ],
        },
    }
