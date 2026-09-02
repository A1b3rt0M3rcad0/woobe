from modules.network.application.dtos.execution import (
    AcceptNetworkExecutionInput,
    AcceptedNetworkExecution,
)
from modules.network.application.dtos.public_runtime import SubmitPublicNetworkRunInput
from modules.network.application.dtos.sessions import CreateNetworkSessionInput, NetworkSessionOutput
from modules.network.application.interfaces.execution_repository import (
    NetworkExecutionAcceptanceRepository,
)
from modules.network.application.interfaces.use_case import UseCase
from modules.network.domain.enums import NetworkEnvironment
from shared.contracts.errors import NotFoundError


class SubmitPublicNetworkRunUseCase:
    def __init__(
        self,
        acceptance_repository: NetworkExecutionAcceptanceRepository,
        create_session: UseCase[NetworkSessionOutput],
        accept_execution: UseCase[AcceptedNetworkExecution],
    ) -> None:
        self._acceptance_repository = acceptance_repository
        self._create_session = create_session
        self._accept_execution = accept_execution

    async def execute(
        self,
        input_dto: SubmitPublicNetworkRunInput,
    ) -> AcceptedNetworkExecution:
        if input_dto.idempotency_key:
            existing = await self._acceptance_repository.find_idempotent(
                network_id=input_dto.network_id,
                idempotency_key=input_dto.idempotency_key,
            )
            if existing is not None:
                if existing.project_id != input_dto.project_id:
                    raise NotFoundError("Network execution not found")
                existing_session = await self._acceptance_repository.get_session(
                    network_id=input_dto.network_id,
                    project_id=input_dto.project_id,
                    network_session_id=existing.network_session_id,
                    lock=False,
                )
                if (
                    existing_session is None
                    or existing_session.environment != input_dto.environment
                ):
                    raise NotFoundError("Network execution not found")
                return existing

        session_id = input_dto.session_id
        if session_id is None:
            network_session = await self._create_session.execute(
                CreateNetworkSessionInput(
                    project_id=input_dto.project_id,
                    network_id=input_dto.network_id,
                    environment=NetworkEnvironment(input_dto.environment),
                    title="Runtime session",
                    tenant_id=input_dto.tenant_id or str(input_dto.project_id),
                    user_id=input_dto.user_id,
                    external_session_id=None,
                )
            )
            session_id = network_session.id

        return await self._accept_execution.execute(
            AcceptNetworkExecutionInput(
                project_id=input_dto.project_id,
                network_id=input_dto.network_id,
                network_session_id=session_id,
                message=input_dto.message,
                idempotency_key=input_dto.idempotency_key,
                expected_environment=input_dto.environment,
            )
        )
