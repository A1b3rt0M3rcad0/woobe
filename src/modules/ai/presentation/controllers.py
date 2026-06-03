from uuid import UUID

from fastapi import APIRouter, Depends, Query

from modules.ai.application.providers import (
    get_create_agent_use_case,
    get_create_provider_credential_use_case,
    get_agent_by_id_use_case,
    get_update_agent_use_case,
)
from modules.ai.infra.repositories import (
    SQLAlchemyAgentRepository,
    SQLAlchemyProviderCredentialRepository,
)
from modules.ai.presentation.mappers import agent_to_response
from modules.ai.presentation.schemas import (
    AgentResponse,
    CreateAgentRequest,
    CreateProviderCredentialRequest,
    ProviderCredentialResponse,
    UpdateAgentRequest,
)
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateProviderCredentialInput,
    UpdateAgentInput,
)
from shared.presentation.dependencies import get_session_manager
from shared.presentation.responses import created, ok

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/credentials")
async def create_provider_credential(
    request: CreateProviderCredentialRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_create_provider_credential_use_case(manager.session)
    input_dto = CreateProviderCredentialInput(
        project_id=request.project_id,
        provider=request.provider,
        name=request.name,
        secret=request.secret,
        metadata=request.metadata,
    )
    result = await use_case.execute(input_dto)
    return created(ProviderCredentialResponse(**result.model_dump()))


@router.get("/credentials")
async def list_provider_credentials(
    project_id: UUID | None = Query(None),
    manager=Depends(get_session_manager),
):
    if not project_id:
        return ok([])
    repo = SQLAlchemyProviderCredentialRepository(manager.session)
    credentials = await repo.list_by_project(project_id)
    return ok([ProviderCredentialResponse(
        id=c.id,
        project_id=c.project_id,
        provider=c.provider,
        name=c.name,
        status=c.status,
        created_at=c.created_at,
        metadata=c.metadata,
    ) for c in credentials])


@router.post("/agents")
async def create_agent(
    request: CreateAgentRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_create_agent_use_case(manager.session)
    input_dto = CreateAgentInput(
        project_id=request.project_id,
        name=request.name,
        provider=request.provider,
        model=request.model,
        system_prompt=request.system_prompt,
        description=request.description,
        provider_credential_id=request.provider_credential_id,
        temperature=request.temperature,
        max_output_tokens=request.max_output_tokens,
        fallback_provider=request.fallback_provider,
        fallback_model=request.fallback_model,
        fallback_credential_id=request.fallback_credential_id,
        session_mode=request.session_mode or "stateful",
        settings=request.settings,
    )
    result = await use_case.execute(input_dto)
    return created(agent_to_response(result))


@router.get("/agents")
async def list_agents(
    project_id: UUID | None = Query(None),
    manager=Depends(get_session_manager),
):
    if not project_id:
        return ok([])
    repo = SQLAlchemyAgentRepository(manager.session)
    agents = await repo.list_by_project(project_id)
    return ok([agent_to_response(a) for a in agents])


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = get_agent_by_id_use_case(manager.session)
    result = await use_case.execute(agent_id)
    return ok(agent_to_response(result))


@router.patch("/agents/{agent_id}")
async def update_agent(
    agent_id: UUID,
    request: UpdateAgentRequest,
    manager=Depends(get_session_manager),
):
    use_case = get_update_agent_use_case(manager.session)
    raw = request.model_dump(exclude_unset=True)
    input_dto = UpdateAgentInput(**raw)
    result = await use_case.execute(agent_id, input_dto)
    return ok(agent_to_response(result))
