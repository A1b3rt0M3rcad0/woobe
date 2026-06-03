from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends

from modules.tools.application.providers import (
    provide_create_secret_uc,
    provide_create_tool_uc,
    provide_list_tools_by_agent,
)
from modules.tools.presentation.schemas import (
    CreateSecretRequest,
    CreateToolRequest,
    SecretResponse,
    ToolResponse,
)
from modules.tools.service.dtos import CreateSecretInput, CreateToolInput
from shared.domain.errors import ConflictError, NotFoundError, ValidationError
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, error, ok

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/tools")
async def create_tool(
    body: CreateToolRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_create_tool_uc(manager.session)
        dto = CreateToolInput(
            project_id=body.project_id,
            agent_id=body.agent_id,
            name=body.name,
            description=body.description,
            type=body.type,
            config=body.config,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            risk_level=body.risk_level,
            timeout_ms=body.timeout_ms,
        )
        result = await uc.execute(dto)
        return created(
            ToolResponse(
                id=result.id,
                project_id=result.project_id,
                agent_id=result.agent_id,
                name=result.name,
                description=result.description,
                type=result.type,
                config=result.config,
                input_schema=result.input_schema,
                output_schema=result.output_schema,
                risk_level=result.risk_level,
                timeout_ms=result.timeout_ms,
                status=result.status,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )
    except ConflictError as e:
        return error(str(e), status_code=409)
    except ValidationError as e:
        return error(str(e), status_code=422)


@router.get("/agents/{agent_id}/tools")
async def list_tools_by_agent(
    agent_id: UUID,
    manager=Depends(get_session_manager),
):
    try:
        tools = await provide_list_tools_by_agent(manager.session, agent_id)
        return ok(
            [
                ToolResponse(
                    id=t.id,
                    project_id=t.project_id,
                    agent_id=t.agent_id,
                    name=t.name,
                    description=t.description,
                    type=t.type,
                    config=t.config,
                    input_schema=t.input_schema,
                    output_schema=t.output_schema,
                    risk_level=t.risk_level,
                    timeout_ms=t.timeout_ms,
                    status=t.status,
                    created_at=t.created_at,
                    updated_at=t.updated_at,
                )
                for t in tools
            ]
        )
    except NotFoundError as e:
        return error(str(e), status_code=404)


@router.post("/secrets")
async def create_secret(
    body: CreateSecretRequest,
    manager=Depends(get_session_manager),
):
    try:
        uc = provide_create_secret_uc(manager.session)
        dto = CreateSecretInput(
            project_id=body.project_id,
            name=body.name,
            type=body.type,
            value=body.value,
        )
        result = await uc.execute(dto)
        return created(
            SecretResponse(
                id=result.id,
                project_id=result.project_id,
                name=result.name,
                type=result.type,
                data=result.data,
                created_at=result.created_at,
                updated_at=result.updated_at,
            )
        )
    except ConflictError as e:
        return error(str(e), status_code=409)
    except ValidationError as e:
        return error(str(e), status_code=422)
