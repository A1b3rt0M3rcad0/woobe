from uuid import UUID

from fastapi import APIRouter, Depends

from modules.ai.application.providers import (
    get_create_agent_use_case,
    get_create_provider_credential_use_case,
    get_agent_by_id_use_case,
)
from modules.ai.presentation.schemas import (
    AgentResponse,
    CreateAgentRequest,
    CreateProviderCredentialRequest,
    ProviderCredentialResponse,
)
from modules.ai.service.dtos import (
    CreateAgentInput,
    CreateProviderCredentialInput,
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
    )
    result = await use_case.execute(input_dto)
    return created(ProviderCredentialResponse(**result.model_dump()))


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
        temperature=request.temperature,
        max_output_tokens=request.max_output_tokens,
        settings=request.settings,
    )
    result = await use_case.execute(input_dto)
    return created(AgentResponse(**result.model_dump()))


@router.get("/agents/{agent_id}")
async def get_agent(
    agent_id: UUID,
    manager=Depends(get_session_manager),
):
    use_case = get_agent_by_id_use_case(manager.session)
    result = await use_case.execute(agent_id)
    return ok(AgentResponse(**result.model_dump()))
