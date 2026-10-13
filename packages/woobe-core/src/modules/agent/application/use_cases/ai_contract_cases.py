from uuid import UUID
from modules.agent.domain.contract_definition import contract_schema_hash

from shared.contracts.errors import ConflictError, ValidationError

from modules.agent.application.dtos.ai_dtos import CreateContractInput, CreateContractOutput, ListContractsOutput, UpdateContractInput, UpdateContractOutput
from modules.agent.domain.entities import AgentContract
from modules.agent.domain.enums import ContractStatus
from modules.agent.application.interfaces.repositories import AgentContractRepository


def _normalize_contract(item):
    item.name = (item.name or "").strip() or f"Contract {item.version}"
    if len(item.name) > 255:
        raise ValidationError("Contract name must contain at most 255 characters")
    if item.repair_attempts is None or item.repair_attempts < 0:
        raise ValidationError("Contract repair_attempts must be nonnegative")
    if item.validation_mode is None or item.status is None:
        raise ValidationError("Contract validation_mode and status cannot be null")
    item.input_schema = item.input_schema or {}
    item.output_schema = item.output_schema or {}
    item.additional_instructions = item.additional_instructions or ""
    item.schema_hash = contract_schema_hash(item.input_schema, item.output_schema)
    return item


def _to_output(saved: AgentContract):
    return CreateContractOutput(
        id=saved.id,
        project_id=saved.project_id,
        agent_id=saved.agent_id,
        version=saved.version,
        name=saved.name,
        input_schema=saved.input_schema,
        output_schema=saved.output_schema,
        validation_mode=saved.validation_mode,
        repair_attempts=saved.repair_attempts,
        additional_instructions=saved.additional_instructions,
        schema_hash=saved.schema_hash,
        status=saved.status,
        created_at=saved.created_at,
        updated_at=saved.updated_at,
    )


class CreateContractUseCase:
    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, input_dto: CreateContractInput) -> CreateContractOutput:
        saved = await self._contract_repo.save(_normalize_contract(AgentContract(
            project_id=input_dto.project_id,
            agent_id=input_dto.agent_id,
            version=input_dto.version,
            name=input_dto.name,
            input_schema=input_dto.input_schema,
            output_schema=input_dto.output_schema,
            validation_mode=input_dto.validation_mode,
            repair_attempts=input_dto.repair_attempts,
            additional_instructions=input_dto.additional_instructions,
            schema_hash=input_dto.schema_hash,
            status=ContractStatus.draft,
        )))
        return _to_output(saved)


class UpdateContractUseCase:
    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, contract_id: UUID, input_dto: UpdateContractInput) -> UpdateContractOutput:
        item = await self._contract_repo.get_by_id(contract_id)
        if item is None:
            from modules.agent.domain.errors import ContractNotFoundError
            raise ContractNotFoundError
        observed = item.updated_at
        if input_dto.expected_updated_at is not None and input_dto.expected_updated_at != observed:
            raise ConflictError("Contract changed; read its updated_at before retrying")
        for field, value in input_dto.model_dump(exclude_unset=True, exclude={"expected_updated_at"}).items():
            setattr(item, field, value)
        saved = await self._contract_repo.update(_normalize_contract(item), expected_updated_at=observed)
        return UpdateContractOutput(**_to_output(saved).model_dump())


class ListContractsUseCase:
    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, agent_id: UUID) -> list[ListContractsOutput]:
        return [ListContractsOutput(id=item.id, version=item.version, name=item.name, validation_mode=item.validation_mode, status=item.status, created_at=item.created_at) for item in await self._contract_repo.list_by_agent(agent_id)]


class GetContractUseCase:
    def __init__(self, contract_repo: AgentContractRepository) -> None:
        self._contract_repo = contract_repo

    async def execute(self, contract_id: UUID) -> AgentContract:
        item = await self._contract_repo.get_by_id(contract_id)
        if item is None:
            from modules.agent.domain.errors import ContractNotFoundError
            raise ContractNotFoundError
        return item
